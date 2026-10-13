#!/usr/bin/env python3
"""Portable source/APK/invocation validators; no device execution or application imports."""
import hashlib
import json
import math
import re
from urllib.parse import urlsplit
from zipfile import ZipFile

STAMP = "assets/pocketchat-integration-build.json"
PACKAGE = "local.pocketchat.test"
GUARD_CHECK_NAMES = (
    'Closed guard route evidence did not overflow',
    'Closed guard returns the blocked actual route for fetch GET',
    'Closed guard returns the blocked actual route for HTTP Worker',
    'Closed guard receives owned actual native callback',
    'Closed guard fetch terminates in an actual network rejection',
    'Closed guard HTTP Worker terminates in a trusted error event',
    'Closed guard accepts no new controlled TCP connection',
    'Closed guard parses no new controlled request',
    'Controlled listener remains bound after actual guard rejection',
)


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



def verify_guard_evidence(report):
    """Validate device observations without manufacturing missing receipts."""
    def require(condition, message):
        if not condition:
            raise ValueError('Actual closed-guard evidence is incomplete: ' + message)

    def integer(value, minimum=0):
        return type(value) is int and minimum <= value <= 2**63 - 1

    def clock(value):
        try:
            return type(value) in (int, float) and math.isfinite(value) and value >= 0
        except OverflowError:
            return False

    verify(report, 138, True)
    checks = report['checks']
    require(type(report.get('total')) is int, 'total assertion count')
    require(all(isinstance(row, dict) and isinstance(row.get('name'), str) for row in checks), 'named checks')
    require([row['name'] for row in checks if row['name'] in GUARD_CHECK_NAMES] == list(GUARD_CHECK_NAMES),
            'the nine ordered, unique guard checks')
    source, nonce = report.get('sourceCommit'), report.get('runNonce')
    require(isinstance(source, str) and re.fullmatch('[0-9a-f]{40}', source), 'source commit')
    require(isinstance(nonce, str) and re.fullmatch('[0-9a-f]{32}', nonce), 'invocation nonce')
    identity = report.get('buildIdentity')
    require(isinstance(identity, dict) and identity.get('sourceCommit') == source
            and identity.get('dirtySource') is False, 'installed source ownership')
    origin = report.get('origin')
    require(isinstance(origin, str), 'controlled origin')
    try:
        port = urlsplit(origin).port
    except ValueError as error:
        raise ValueError('Malformed controlled origin') from error
    require(integer(port, 1) and port <= 65535 and origin == 'http://127.0.0.1:' + str(port),
            'exact loopback HTTP authority')
    guard = report.get('guardEvidence')
    require(isinstance(guard, dict) and guard.get('status') == 'passed', 'successful guard phase')
    fresh = guard.get('nonce')
    require(isinstance(fresh, str) and re.fullmatch('[0-9a-f]{32}', fresh) and fresh != nonce, 'fresh guard nonce')
    document = origin + '/page?run=' + nonce + '&case=4&session=primary'
    fetch_url = origin + '/echo?run=' + fresh + '&case=4&session=primary&kind=guard-fetch'
    worker_url = origin + '/worker?run=' + fresh + '&case=4&session=primary'
    require(guard.get('document') == document and guard.get('fetchUrl') == fetch_url
            and guard.get('workerUrl') == worker_url, 'owned document and complete request URIs')
    session = guard.get('nativeSession')
    require(integer(session, 1), 'captured native session')
    cases = report.get('cases')
    require(isinstance(cases, list) and len(cases) == 4, 'four original cases')
    primary, runtime = None, None
    for index, case in enumerate(cases):
        require(isinstance(case, dict) and type(case.get('index')) is int and case['index'] == index
                and type(case.get('serial')) is int and case['serial'] == index + 1
                and case.get('status') == 'passed', 'original case identity')
        rows = case.get('sessions')
        names = ['primary', 'secondary'] if index == 3 else ['primary']
        require(isinstance(rows, list) and all(isinstance(row, dict) and isinstance(row.get('name'), str) for row in rows)
                and sorted(row['name'] for row in rows) == names, 'original session ownership')
        for row in rows:
            native, observed = row.get('native'), row.get('observed')
            require(isinstance(native, dict) and integer(native.get('session'), 1)
                    and integer(native.get('runtime'), 1), 'original native identities')
            if runtime is None:
                runtime = native['runtime']
            require(native['runtime'] == runtime, 'same original runtime')
            require(isinstance(observed, dict) and observed.get('run') == nonce
                    and type(observed.get('case')) is int and observed['case'] == index + 1
                    and observed.get('session') == row['name'], 'original context invocation')
            require(native['session'] == session if row['name'] == 'primary' else native['session'] != session,
                    'same primary and distinct secondary native sessions')
            if index == 3 and row['name'] == 'primary':
                primary = row
    native_port = guard.get('nativePort')
    require(isinstance(native_port, dict) and type(native_port.get('nativeSession')) is int
            and native_port['nativeSession'] == session and native_port.get('senderUrl') == document
            and native_port.get('topLevel') is True and type(native_port.get('environmentType')) is int
            and native_port['environmentType'] == 2, 'actual top-level content-script sender')
    require(guard.get('armCallback') == '"guard-armed"', 'original SDK immediate JSON arm callback')
    times = [guard.get('requestedAt'), native_port.get('connectedAt'),
             guard.get('nativeCallbackAt'), guard.get('completedAt')]
    require(all(integer(value) for value in times) and times == sorted(times), 'ordered native elapsed clocks')
    require(integer(cases[-1].get('completedAt')) and cases[-1]['completedAt'] <= times[0],
            'guard follows original observations')
    observed = guard.get('observed')
    require(isinstance(observed, dict) and observed.get('nonce') == fresh
            and observed.get('fetchUrl') == fetch_url and observed.get('workerUrl') == worker_url,
            'actual event invocation and targets')
    fetch, worker = observed.get('fetch'), observed.get('worker')
    require(isinstance(fetch, dict) and fetch.get('outcome') == 'network-error'
            and isinstance(fetch.get('name'), str) and bool(fetch['name'])
            and isinstance(fetch.get('message'), str), 'actual fetch rejection')
    require(isinstance(worker, dict) and worker.get('outcome') == 'error'
            and worker.get('trusted') is True and isinstance(worker.get('message'), str), 'trusted worker error')
    parent = primary['observed'].get('parent')
    require(isinstance(parent, dict), 'original primary document clock')
    page_times = [parent.get('at'), fetch.get('at'), worker.get('at'), observed.get('at')]
    require(all(clock(value) for value in page_times) and page_times[0] <= min(page_times[1:3])
            and max(page_times[1:3]) <= page_times[3], 'ordered primary performance clocks')
    routes = guard.get('blockedRoutes')
    require(type(guard.get('blockedRoutesDropped')) is int and guard['blockedRoutesDropped'] == 0
            and isinstance(routes, list) and 2 <= len(routes) <= 8, 'complete bounded route observations')
    targets = set()
    for row in routes:
        require(isinstance(row, dict) and row.get('url') in (fetch_url, worker_url)
                and row.get('guardAllowed') is False and integer(row.get('at'))
                and times[0] <= row['at'] <= times[2], 'owned actual blocked route callback')
        proxy = row.get('route')
        require(isinstance(proxy, dict) and proxy.get('type') == 'socks'
                and proxy.get('host') == '127.0.0.1' and type(proxy.get('port')) is int and proxy['port'] == 9
                and proxy.get('proxyDNS') is True and type(proxy.get('failoverTimeout')) is int
                and proxy['failoverTimeout'] == 1, 'closed bootstrap proxy receipt')
        targets.add(row['url'])
    require(targets == {fetch_url, worker_url}, 'both actual attempted routes')
    snapshots = [guard.get('beforeServer'), guard.get('afterServer')]
    for snapshot in snapshots:
        require(isinstance(snapshot, dict) and snapshot.get('address') == '127.0.0.1'
                and type(snapshot.get('port')) is int and snapshot['port'] == port
                and snapshot.get('bound') is True and snapshot.get('closed') is False, 'live owned listener')
        require(all(integer(snapshot.get(key)) for key in ('acceptedConnections', 'parsedRequests',
                'completedConnections', 'rejectedConnections', 'failuresDropped')), 'actual nonnegative listener counters')
        require(isinstance(snapshot.get('failures'), list) and len(snapshot['failures']) <= 16, 'bounded server failures')
    before, after = snapshots
    require(before['acceptedConnections'] == after['acceptedConnections']
            and before['parsedRequests'] == after['parsedRequests'], 'no new controlled connection or request')
    header_counts = [guard.get('beforeHeaderCount'), guard.get('afterHeaderCount')]
    headers = report.get('allRequestHeaders')
    require(all(integer(value, 30) for value in header_counts) and header_counts[0] == header_counts[1]
            and isinstance(headers, list) and len(headers) == header_counts[1], 'no new actual first-party header record')


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
    verify_guard_evidence(report)

