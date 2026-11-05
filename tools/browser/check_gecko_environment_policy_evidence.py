#!/usr/bin/env python3
"""Check source-bound Android Gecko environment-policy observations, never invent them.

This checker can reject inconsistent receipts; it cannot turn synthetic input
into proof of device execution. Its unit tests use synthetic reports only.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gecko.profile_invocation_contract import verify_installed
from gecko.sdk_identity_contract import SDK_FIELDS, _typed_equal, source_bytes, strict_json
from check_fingerprint_evidence import validate_host_trust

REPORT_NAME = 'gecko-environment-policy-results.json'
FIXTURE_TYPE = 'gecko-production-environment-policy-v1'
ORIGINS = {'https://fp-a.pocketchat.test', 'https://fp-b.pocketchat.test'}
LABELS = ('system', 'new-york', 'coop', 'kathmandu', 'reload', 'reopen', 'restore', 'desktop', 'mobile-restored')
FULL_WORKER_LABELS = {'system', 'new-york', 'kathmandu', 'desktop', 'mobile-restored'}
WORKER_ROLES = {'classic': 'dedicated-classic', 'module': 'dedicated-module', 'blob': 'dedicated-blob', 'shared': 'shared-worker', 'service': 'service-worker-fetch'}
SCRIPT_PATHS = {'classic': '/dedicated.js', 'module': '/module.js', 'shared': '/shared.js', 'service': '/service.js'}
REQUIRED = {
    'gecko.production-main', 'trust.enterprise-roots', 'bridge.exact-session-context',
    'clock.system', 'clock.new-york', 'clock.coop', 'clock.kathmandu',
    'navigation.reload', 'navigation.reopen', 'navigation.restore',
    'stale.actual-store-record-rejected', 'popup.custom-rejected',
    'rfp.conflict-preserves-protection', 'ua.mobile.native', 'ua.desktop.native',
    'ua.mobile-restored.native', 'wire.public-only', 'gpt.generic-hotpath-off',
    'coverage.worker-scopes-honest',
}
SOURCE_INPUTS = {
    'tools/browser/check_gecko_environment_policy_evidence.py',
    'tools/browser/run_gecko_environment_policy_integration.py',
    'tools/browser/newworker_fixture_server.py',
    'tools/browser/fingerprint_fixture_server.py',
    'tools/browser/check_fingerprint_evidence.py',
    'tools/gecko/profile_invocation_contract.py',
    'tools/gecko/sdk_identity_contract.py',
    'tests/gecko/GeckoEnvironmentPolicyIntegrationActivity.java',
    'tests/gecko/GeckoEnvironmentPolicyProvider.java',
    'tests/gecko/BrowserFingerprintFixture.java',
    'tests/gecko/IntegrationBuildIdentity.java',
    'tests/gecko/assets/gecko-environment-policy-page.js',
    'tests/gecko/AndroidManifest.xml',
    'tests/gecko/res/xml/network_security.xml',
    'app/build.gradle', 'app/src/main/AndroidManifest.xml',
    'app/src/main/res/xml/network_security.xml',
    '.github/workflows/browser-2_1-acceptance.yml',
    'app/src/main/java/local/pocketchat/ChatSession.java',
    'app/src/main/java/local/pocketchat/GeckoWebView.java',
    'app/src/main/java/local/pocketchat/GeckoPolicyAdapter.java',
    'app/src/main/java/local/pocketchat/GeckoTimeZoneController.java',
    'app/src/main/java/local/pocketchat/GeckoTimeZoneStore.java',
    'app/src/main/java/local/pocketchat/GeckoTimeZonePolicy.java',
    'app/src/main/java/local/pocketchat/GeckoTimeZoneSpec.java',
    'app/src/main/java/local/pocketchat/GeckoTimeZoneUi.java',
    'app/src/main/java/local/pocketchat/BrowserBridgeRequests.java',
    'app/src/main/java/org/mozilla/geckoview/AppSessionIdentity.java',
    'app/src/main/assets/gecko/manifest.json',
    'app/src/main/assets/gecko/background.js',
    'app/src/main/assets/gecko/request-headers.js',
    'app/src/main/assets/gecko/request-identity-background.js',
    'app/src/main/assets/gecko/native-timezone-bridge.js',
    'app/src/main/assets/gecko/native-timezone-api.js',
    'app/src/main/assets/gecko/native-timezone-schema.json',
}
ACK_KEYS = {'schema', 'status', 'requestToken', 'sessionId', 'requestedZoneId', 'nativeZoneId', 'contextId', 'nativeSettingReadback', 'scope', 'workerCoverageVerified', 'serviceWorkerCoverageVerified'}
RECEIPT_KEYS = {'schema', 'identity', 'desiredRevision', 'processNonce', 'requestToken', 'binding', 'nativeSettingReadback', 'pageObservationVerified', 'workerCoverageVerified', 'serviceWorkerCoverageVerified', 'nativeReceipt', 'recordedAt'}
CLOCK_FIELDS = {'offsetMinutes', 'year', 'month', 'day', 'hour', 'minute'}
ZONE_ALIASES = ({'Asia/Kathmandu', 'Asia/Katmandu'}, {'UTC', 'Etc/UTC', 'Etc/GMT', 'GMT', 'UCT', 'Etc/UCT', 'Universal', 'Zulu'})


def require(value, message):
    if not value:
        raise ValueError('Gecko environment policy acceptance: ' + message)


def integer(value, minimum=0, maximum=2**63-1):
    return type(value) is int and minimum <= value <= maximum


def token(value, pattern=r'[A-Za-z0-9_.:-]{1,160}'):
    return type(value) is str and re.fullmatch(pattern, value) is not None


def sha(value, size=64):
    return token(value, '[0-9a-f]{' + str(size) + '}')


def ua(value):
    return type(value) is str and 1 <= len(value) <= 1024 and all(32 <= ord(char) <= 126 for char in value)


def zone(value):
    require(type(value) is str and 0 < len(value) <= 80 and re.fullmatch(r'[A-Za-z0-9_+/\-]+', value), 'bounded IANA timezone required')
    try:
        return ZoneInfo(value)
    except (ValueError, ZoneInfoNotFoundError) as error:
        raise ValueError('Gecko environment policy acceptance: unknown IANA timezone') from error


def expected_clock(zone_id):
    selected = zone(zone_id)
    result = {'timeZone': zone_id}
    for key, month in (('january', 1), ('july', 7)):
        local = datetime(2026, month, 15, 12, tzinfo=timezone.utc).astimezone(selected)
        result[key] = dict(offsetMinutes=-int(local.utcoffset().total_seconds() // 60), year=local.year, month=local.month, day=local.day, hour=local.hour, minute=local.minute)
    return result


def clock(value):
    require(type(value) is dict and set(value) == {'timeZone', 'january', 'july'}, 'complete raw Date/Intl clock required')
    zone(value.get('timeZone'))
    for key, month in (('january', 1), ('july', 7)):
        row = value.get(key)
        require(type(row) is dict and set(row) == CLOCK_FIELDS and all(type(row.get(field)) is int for field in CLOCK_FIELDS), 'typed six-field January/July clock required')
        require(-840 <= row['offsetMinutes'] <= 840 and row['year'] == 2026 and row['month'] == month and 14 <= row['day'] <= 16 and 0 <= row['hour'] < 24 and 0 <= row['minute'] < 60, 'raw fixed-epoch clock out of range')
    return value


def same_zone(actual, expected):
    return actual == expected or any(actual in group and expected in group for group in ZONE_ALIASES)


def clock_matches(value, zone_id):
    clock(value)
    expected = expected_clock(zone_id)
    return same_zone(value['timeZone'], zone_id) and all(_typed_equal(value[key], expected[key]) for key in ('january', 'july'))


def clock_difference(value, zone_id, **identity):
    expected = expected_clock(zone_id)
    fields = [] if same_zone(value['timeZone'], zone_id) else ['timeZone']
    fields += [season + '.' + field for season in ('january', 'july') for field in sorted(CLOCK_FIELDS) if not _typed_equal(value[season][field], expected[season][field])]
    return dict(identity, timeZone=value['timeZone'], desiredTimeZone=zone_id, differentFields=fields, observation=value, expected=expected)


def unclaimed(value):
    require(value.get('workerCoverageVerified') is False and value.get('serviceWorkerCoverageVerified') is False, 'whole Worker or Service Worker timezone coverage must not be claimed')


def environment(value):
    require(type(value) is dict and set(value) == {'slot', 'generation', 'environmentId'} and integer(value.get('slot'), 0, 7) and integer(value.get('generation')) and token(value.get('environmentId'), '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'), 'exact environment slot/generation/id required')
    return value


def native_sample(value, desired, engine_version):
    require(type(value) is dict and ua(value.get('userAgent')) and type(value.get('desktop')) is bool and token(value.get('sessionId')) and token(value.get('sessionEpoch')) and token(value.get('contextId'), '[1-9][0-9]{0,23}') and integer(value.get('desiredRevision'), 1) and value.get('desiredZone') == desired, 'exact current native session/epoch/context/revision/zone/UA required')
    receipt = value.get('receipt')
    require(type(receipt) is dict and set(receipt) == RECEIPT_KEYS and receipt.get('schema') == 1 and type(receipt.get('schema')) is int and receipt.get('desiredRevision') == value['desiredRevision'] and type(receipt.get('desiredRevision')) is int and sha(receipt.get('processNonce')) and sha(receipt.get('requestToken')) and integer(receipt.get('recordedAt'), 1), 'full current encrypted-sidecar receipt required')
    owner = environment(receipt.get('identity'))
    binding = receipt.get('binding')
    require(type(binding) is dict and set(binding) == {'engineVersion', 'sessionId', 'sessionEpoch', 'contextId'} and binding.get('engineVersion') == engine_version, 'exact selected-engine native receipt binding required')
    for key in ('sessionId', 'sessionEpoch', 'contextId'):
        require(binding.get(key) == value[key], 'sidecar receipt belongs to a different ' + key)
    require(receipt.get('nativeSettingReadback') is True and receipt.get('pageObservationVerified') is False, 'sidecar native readback must not claim page effects')
    unclaimed(receipt)
    actual = receipt.get('nativeReceipt')
    require(type(actual) is dict and set(actual) == ACK_KEYS and type(actual.get('schema')) is int and actual['schema'] == 1 and actual.get('status') == 'applied' and actual.get('scope') == 'top-browsing-context' and actual.get('nativeSettingReadback') is True, 'exact successful native setting ACK required')
    require(actual.get('requestToken') == receipt['requestToken'] and actual.get('sessionId') == value['sessionId'] and actual.get('contextId') == value['contextId'] and actual.get('requestedZoneId') == desired and actual.get('nativeZoneId') == desired, 'native ACK token/session/context/requested/native zone mismatch')
    unclaimed(actual)
    fresh = value.get('freshReadback')
    require(value.get('contextCurrent') is True and type(fresh) is dict and set(fresh) == ACK_KEYS and type(fresh.get('schema')) is int and fresh['schema'] == 1 and fresh.get('status') == 'read' and fresh.get('scope') == 'top-browsing-context' and fresh.get('nativeSettingReadback') is True and sha(fresh.get('requestToken')) and fresh['requestToken'] != receipt['requestToken'] and fresh.get('sessionId') == value['sessionId'] and fresh.get('contextId') == value['contextId'] and fresh.get('requestedZoneId') == fresh.get('nativeZoneId') == desired, 'fresh private native context read must agree with the current stored setting receipt')
    unclaimed(fresh)
    policy = value.get('timeZonePolicy')
    require(type(policy) is dict and type(policy.get('schema')) is int and policy['schema'] == 1 and policy.get('engine') == 'gecko' and policy.get('loaded') is True and policy.get('desiredZone') == desired and policy.get('desiredRevision') == value['desiredRevision'] and type(policy.get('desiredRevision')) is int and policy.get('state') == 'native-readback' and policy.get('nativeSettingReadback') is True and policy.get('scope') == policy.get('appliedScope') == 'top-browsing-context' and policy.get('pageObservationVerified') is False and ('currentSessionPrepared' not in policy or policy['currentSessionPrepared'] is True) and not policy.get('issue'), 'current controller native-readback status required')
    unclaimed(policy)
    header = value.get('headerPolicy')
    require(type(header) is dict and header.get('installed') is True and header.get('nativeReadback') is True and header.get('scope') == 'public-http-request-ua-only' and header.get('privateAdmission') == 'unchanged-original-headers' and header.get('userAgent') == value['userAgent'] and integer(header.get('revision'), 1) and header.get('sharedWorkerWireVerified') is False and header.get('serviceWorkerWireVerified') is False, 'actual current public HTTP UA policy readback required')
    return owner


def source_hashes(report, source, reader):
    hashes = report.get('sourceFiles')
    require(type(hashes) is dict and SOURCE_INPUTS <= set(hashes) and len(hashes) <= 2000, 'required production/integration source hashes missing')
    for path, digest in hashes.items():
        require(type(path) is str and path and str(PurePosixPath(path)) == path and not PurePosixPath(path).is_absolute() and '..' not in PurePosixPath(path).parts and '\\' not in path and '\0' not in path and sha(digest), 'unsafe or invalid source hash record')
        require(hashlib.sha256(reader(source, path)).hexdigest() == digest, 'selected-source bytes differ: ' + path)


def selected_engine_version(source, reader):
    raw = reader(source, 'app/src/main/java/local/pocketchat/GeckoWebView.java').decode('utf-8')
    versions = re.findall(r'^\s*static final String VERSION=("(?:[^"\\]|\\.)*");', raw, flags=re.MULTILINE)
    require(len(versions) == 1, 'unique selected production Gecko engine version required')
    version = json.loads(versions[0])
    require(type(version) is str and 1 <= len(version) <= 128 and '\0' not in version, 'selected production engine version invalid')
    return version


def proof_lifecycle(activity, samples):
    lifecycle = activity.get('lifecycle')
    require(type(lifecycle) is dict and set(lifecycle) == {'reload', 'reopen', 'restore', 'coop'}, 'complete actual lifecycle proof required')
    for label, before_label in (('reload', 'kathmandu'), ('reopen', 'reload')):
        row = lifecycle.get(label)
        before, after = samples[before_label], samples[label]
        require(type(row) is dict and row.get('beforeDocumentId') == before['page']['documentId'] and row.get('afterDocumentId') == after['page']['documentId'] and row.get('beforeContextId') == before['native']['contextId'] and row.get('afterContextId') == after['native']['contextId'] and row['beforeDocumentId'] != row['afterDocumentId'], 'lifecycle document/context binding differs: ' + label)
        if label == 'reopen':
            require(row['beforeContextId'] != row['afterContextId'], 'reopen must create a fresh native context')
    restore = lifecycle.get('restore')
    require(type(restore) is dict and restore.get('beforeContextId') == samples['reopen']['native']['contextId'] and restore.get('afterContextId') == samples['restore']['native']['contextId'] and restore['beforeContextId'] != restore['afterContextId'] and restore.get('sdkCheckpointAvailable') is True and restore.get('formValueRestored') is True and integer(restore.get('actualRestoreRequests'), 1), 'actual fresh-context SDK checkpoint restoration missing')
    coop = lifecycle.get('coop')
    require(type(coop) is dict and coop.get('fromOrigin') == samples['new-york']['page']['origin'] and coop.get('toOrigin') == samples['coop']['page']['origin'] and coop.get('fromOrigin') == 'https://fp-a.pocketchat.test' and coop.get('toOrigin') == 'https://fp-b.pocketchat.test' and coop.get('oldContextId') == samples['new-york']['native']['contextId'] and coop.get('newContextId') == samples['coop']['native']['contextId'] and coop.get('firstInlineZoneCorrect') is True and coop.get('responseHeaderObserved') is True and samples['coop']['page']['phase'] == 'gecko-coop', 'actual COOP origin/current-context proof missing')
    require(type(coop.get('contextChanged')) is bool and coop['contextChanged'] is (coop['oldContextId'] != coop['newContextId']), 'COOP native context replacement claim contradicts fresh observations')
    stale = activity.get('staleTicketProof')
    require(type(stale) is dict and all(stale.get(key) is True for key in ('actualStoreRecordAttempt', 'oldRecordRejected', 'oldReceiptEmpty')) and token(stale.get('oldContextId'), '[1-9][0-9]{0,23}') and token(stale.get('newContextId'), '[1-9][0-9]{0,23}') and stale['oldContextId'] != stale['newContextId'] and sha(stale.get('oldToken')) and sha(stale.get('newToken')) and stale['oldToken'] != stale['newToken'], 'actual old sidecar ticket rejection missing')
    require(any(s['native']['contextId'] == stale['oldContextId'] and s['native']['receipt']['requestToken'] == stale['oldToken'] for s in samples.values()) and any(s['native']['contextId'] == stale['newContextId'] and s['native']['receipt']['requestToken'] == stale['newToken'] for s in samples.values()), 'stale ticket tokens do not belong to observed old/new native contexts')
    popup = activity.get('popupProof')
    require(type(popup) is dict and popup.get('actualNavigationDelegate') is True and popup.get('customRejected') is True and popup.get('oldNativeSessionUnchanged') is True and integer(popup.get('sessionCountBefore'), 0, 32) and type(popup.get('sessionCountAfter')) is int and popup['sessionCountBefore'] == popup['sessionCountAfter'], 'custom-zone popup must be rejected by the actual navigation delegate')
    baseline, final = activity['rfpResetBaseline']['native'], activity['rfpFinalObservation']['native']
    require(baseline['desiredZone'] == final['desiredZone'] == '' and baseline['desiredRevision'] == samples['mobile-restored']['native']['desiredRevision'] + 1 and final['desiredRevision'] == baseline['desiredRevision'], 'RFP system reset must have its own actual current native setting baseline')
    conflict = activity.get('rfpConflictProof')
    require(type(conflict) is dict and all(conflict.get(key) is True for key in ('actualUiAttempt', 'rfpConfirmed', 'customSaveRejected')) and type(conflict.get('levelBefore')) is type(conflict.get('levelAfter')) is int and conflict['levelBefore'] == conflict['levelAfter'] == 2 and integer(conflict.get('desiredRevisionBefore'), 1) and type(conflict.get('desiredRevisionAfter')) is int and conflict['desiredRevisionBefore'] == conflict['desiredRevisionAfter'] == baseline['desiredRevision'] and conflict.get('savedZoneBefore') == conflict.get('savedZoneAfter') == baseline['desiredZone'], 'RFP conflict must preserve actual protection and the observed system-reset timezone baseline')


def validate_behavior(report, source, reader=source_bytes):
    require(type(report) is dict and type(report.get('schema')) is int and report['schema'] == 1 and report.get('fixtureType') == FIXTURE_TYPE and report.get('status') == 'passed' and sha(source, 40) and report.get('sourceCommit') == source and sha(report.get('sourceTree'), 40) and sha(report.get('runNonce'), 32), 'successful exact-source fresh invocation required')
    require(report.get('executionInputsUnchanged') is True and not report.get('error'), 'execution inputs changed or wrapper failed')
    for key, expected_flag in (('actualAndroidExecution', True), ('actualGeckoExecution', True), ('actualPublicWebsiteExecution', False), ('workerCoverageVerified', False), ('serviceWorkerCoverageVerified', False)):
        require(key not in report or report[key] is expected_flag, 'wrapper execution or coverage scope contradicts activity')
    cleanup = report.get('cleanup')
    require(type(cleanup) is dict and all(cleanup.get(key) is True for key in ('appStopped', 'reverseRemoved', 'caRemoved', 'privateMaterialRemoved')), 'app/reverse/CA/private-material cleanup missing')
    activity = report.get('activity')
    require(type(activity) is dict and type(activity.get('schema')) is int and activity['schema'] == 1 and activity.get('engine') == 'gecko' and activity.get('status') == 'passed' and activity.get('stage') == 'complete' and not activity.get('failure') and all(activity.get(key) == report[key] for key in ('sourceCommit', 'sourceTree', 'runNonce')), 'completed current Gecko activity identity required')
    require(activity.get('actualAndroidExecution') is True and activity.get('actualGeckoExecution') is True and activity.get('actualPublicWebsiteExecution') is False, 'actual Android Gecko controlled-fixture scope required')
    unclaimed(activity)
    for value in (report, activity):
        require(all(value.get(key) is False for key in ('actualAndroidWebViewExecution', 'actualDesktopChromiumExecution', 'actualDevicePerformanceMeasurement', 'fingerprintProtectionVerified') if key in value), 'unexecuted browser/performance or complete fingerprint coverage must not be claimed')
    require(type(report.get('expectedBuildIdentity')) is dict and _typed_equal(activity.get('buildIdentity'), report['expectedBuildIdentity']) and report['expectedBuildIdentity'].get('sourceCommit') == source and report['expectedBuildIdentity'].get('sourceTree') == report['sourceTree'] and report['expectedBuildIdentity'].get('dirtySource') is False, 'wrapper and installed clean-source build identities differ')
    checks = activity.get('checks')
    require(type(checks) is list and 0 < len(checks) <= 500 and all(type(row) is dict and set(row) == {'id', 'pass'} and token(row.get('id'), '[A-Za-z0-9_.:-]{1,160}') and row.get('pass') is True for row in checks), 'all activity checks must be explicit and passed')
    names = [row['id'] for row in checks]
    require(len(names) == len(set(names)) and REQUIRED <= set(names), 'required checks missing or duplicated')
    system = report.get('systemTimeZone')
    require(type(system) is dict and set(system) == {'zoneId', 'source', 'januaryOffsetMinutes', 'julyOffsetMinutes'} and system.get('source') == 'android-getprop-persist.sys.timezone', 'independent Android system timezone required')
    system_clock = expected_clock(system.get('zoneId'))
    require(type(system.get('januaryOffsetMinutes')) is int and type(system.get('julyOffsetMinutes')) is int and system['januaryOffsetMinutes'] == system_clock['january']['offsetMinutes'] and system['julyOffsetMinutes'] == system_clock['july']['offsetMinutes'], 'Android system offset expectations disagree with host ZoneInfo')
    core_rows = activity.get('samples')
    require(type(core_rows) is list and len(core_rows) == len(LABELS) and all(type(row) is dict for row in core_rows) and [row.get('label') for row in core_rows] == list(LABELS), 'all ordered first-load/policy/lifecycle/UA samples required')
    samples = {row['label']: row for row in core_rows}
    transitions = activity.get('transitionSamples')
    require(type(transitions) is list and len(transitions) == 2 and all(type(row) is dict for row in transitions) and [row.get('label') for row in transitions] == ['desktop-applied', 'mobile-restored-applied'], 'actual template-application document transitions required')
    baseline, final = activity.get('rfpResetBaseline'), activity.get('rfpFinalObservation')
    require(type(baseline) is dict and baseline.get('label') == 'rfp-system-reset' and type(final) is dict and final.get('label') == 'rfp-applied', 'full raw system reset and RFP-application observations required')
    rows = core_rows[:7] + [transitions[0], core_rows[7], transitions[1], core_rows[8], baseline, final]
    engine_version = selected_engine_version(source, reader)
    require(type(report.get('hostTls')) is dict and type(report['hostTls'].get('trustInstallation')) is dict and type(report['expectedBuildIdentity'].get('sdkBuildIdentity')) is dict and type(activity.get('fixture')) is dict, 'host trust/SDK/fixture structures required')
    host = validate_host_trust(report, {'gecko': activity})
    # The shared host validator deliberately has no knowledge of this new
    # fixture's phases or resource roles. Validate its raw bounded HTTP rows here.
    fixture = activity['fixture']
    require(fixture.get('upstreamConnections') == 0 and type(fixture.get('upstreamConnections')) is int and fixture.get('forwardingImplemented') is False and fixture.get('certificateExceptionUsed') is False and integer(fixture.get('tlsConnections'), 1), 'controlled TLS fixture must not forward or bypass trust')
    requests = fixture.get('requests')
    require(type(requests) is list and 0 < len(requests) <= 200 and type(fixture.get('accepted')) is int and fixture['accepted'] == len(requests), 'bounded actual host request snapshot required')
    allowed_headers = {'user-agent', 'sec-ch-ua', 'sec-ch-ua-mobile', 'sec-ch-ua-platform', 'sec-ch-ua-platform-version', 'sec-ch-ua-model', 'sec-ch-ua-arch', 'sec-ch-ua-bitness', 'sec-ch-ua-full-version-list'}
    request_keys = {'origin', 'path', 'tls', 'method', 'phase', 'realm', 'documentId', 'responseCoop'} | allowed_headers
    allowed_paths = {'/env-policy', '/env-frame', '/dedicated.js', '/module.js', '/shared.js', '/service.js', '/worker-probe', '/sw-cached'}
    allowed_realms = {'document', 'frame', 'dedicated-classic', 'dedicated-module', 'dedicated-blob', 'shared-worker', 'service-worker', 'service-worker-install', 'service-worker-fetch'}
    path_realms = {'/env-policy': {'document'}, '/env-frame': {'frame'}, '/dedicated.js': {'dedicated-classic'}, '/module.js': {'dedicated-module'}, '/shared.js': {'shared-worker'}, '/service.js': {'service-worker'}, '/sw-cached': {'service-worker-install'}, '/worker-probe': allowed_realms - {'frame'}}
    for request in requests:
        require(type(request) is dict and set(request) <= request_keys and request.get('origin') in ORIGINS and request.get('path') in allowed_paths and request.get('tls') is True and request.get('method') == 'GET' and token(request.get('phase'), 'gecko-[a-z-]{1,40}') and request.get('realm') in allowed_realms and ua(request.get('user-agent')), 'request escapes HTTPS fixture scope or contains non-allowlisted metadata')
        require(request['realm'] in path_realms[request['path']], 'HTTP fixture resource path/realm mismatch')
        if 'responseCoop' in request:
            require(request.get('responseCoop') == 'same-origin' and request['path'] == '/env-policy' and request['phase'] == 'gecko-coop', 'COOP response trace belongs to a different resource')
        require(request.get('documentId') == '' and request['path'] in {'/env-policy', '/env-frame'} or token(request.get('documentId'), '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'), 'request document incarnation invalid')
        require(all(type(value) is str and len(value) <= 2048 for key, value in request.items() if key in allowed_headers), 'bounded HTTP metadata required')

    def matches(page, realm, path, native_ua, document=None):
        selected = page['documentId'] if document is None else document
        return [row for row in requests if row['origin'] == page['origin'] and row['phase'] == page['phase'] and row['realm'] == realm and row['path'] == path and row['documentId'] == selected and row['user-agent'] == native_ua]

    documents, document_owners, token_bindings, fresh_tokens, owner, process_nonce = set(), {}, {}, set(), None, None
    worker_differences, frame_differences, javascript_ua_differences = [], [], []
    for sample in rows:
        label = sample['label']
        desired = '' if label in {'system', 'rfp-system-reset', 'rfp-applied'} else 'America/New_York' if label in {'new-york', 'coop'} else 'Asia/Kathmandu'
        expected_zone = system['zoneId'] if desired == '' else desired
        native = sample.get('native')
        current_owner = native_sample(native, desired, engine_version)
        if owner is None:
            owner, process_nonce = current_owner, native['receipt']['processNonce']
        require(_typed_equal(current_owner, owner) and native['receipt']['processNonce'] == process_nonce, 'environment identity or app process changed mid-workload')
        request_token = native['receipt']['requestToken']
        current_binding = (native['sessionId'], native['sessionEpoch'], native['contextId'])
        require(request_token not in token_bindings or token_bindings[request_token] == current_binding, 'native setting token was reused for a different session/epoch/context')
        token_bindings[request_token] = current_binding
        require(native['freshReadback']['requestToken'] not in fresh_tokens, 'a native context read token was reused across samples')
        fresh_tokens.add(native['freshReadback']['requestToken'])
        require(native['desktop'] is (label in {'desktop', 'desktop-applied'}), 'sample native desktop mode differs')
        if label in {'desktop-applied', 'mobile-restored-applied'}:
            require(native['desiredRevision'] == samples['mobile-restored']['native']['desiredRevision'], 'template transition changed the saved timezone revision')
        page = sample.get('page')
        parsed = urlsplit(sample.get('url') if type(sample.get('url')) is str else '')
        require(parsed.scheme == 'https' and parsed.hostname in {'fp-a.pocketchat.test', 'fp-b.pocketchat.test'} and parsed.netloc == parsed.hostname and parsed.path == '/env-policy' and not parsed.fragment and parse_qs(parsed.query, strict_parsing=True) == {'phase': [page.get('phase') if type(page) is dict else None]}, 'sample URL is not exact controlled public HTTPS page')
        security = sample.get('security')
        require(type(security) is dict and security.get('isSecure') is True and security.get('isException') is False and security.get('host') == parsed.hostname and security.get('leafDerSha256') == host['leafDerSha256'] and security.get('enterpriseRootsReadback') is True, 'actual native secure peer/leaf/enterprise-roots readback missing')
        raw_pages = [('page', page)] + [('frame', frame) for frame in sample.get('frames', [])] if type(sample.get('frames')) is list else []
        require(len(raw_pages) == 3 and {frame.get('origin') for _, frame in raw_pages[1:] if type(frame) is dict} == ORIGINS, 'same-origin and cross-origin raw frames required')
        for role, raw in raw_pages:
            require(type(raw) is dict and type(raw.get('schema')) is int and raw['schema'] == 1 and raw.get('firstInline') is True and raw.get('secure') is True and raw.get('runNonce') == report['runNonce'] and raw.get('sourceCommit') == source and raw.get('origin') in ORIGINS and token(raw.get('phase'), 'gecko-[a-z-]{1,40}') and raw.get('phase') == page.get('phase') and ua(raw.get('nativeUserAgent')) and raw.get('markerComplete') is True and raw.get('networkAllowed') is True and not raw.get('markerError') and not raw.get('error'), 'fresh first-inline secure page/frame and successful document marker required')
            document = raw.get('documentId')
            require(token(document, '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}') and document not in documents, 'unique page/frame document UUID required')
            documents.add(document)
            document_owners[document] = (raw['phase'], raw['origin'], native['userAgent'])
            actual_clock = clock(raw.get('nativeTimeZone'))
            if role == 'page':
                require(raw['origin'] == 'https://' + parsed.hostname and (label == 'rfp-applied' or clock_matches(actual_clock, expected_zone)), 'first-inline primary Date/Intl does not match current desired timezone')
            elif label != 'rfp-applied' and not clock_matches(actual_clock, expected_zone):
                frame_differences.append(clock_difference(actual_clock, expected_zone, label=label, origin=raw['origin']))
            if raw['nativeUserAgent'] != native['userAgent']:
                javascript_ua_differences.append(dict(label=label, role=role))
            require(matches(raw, 'document', '/worker-probe', native['userAgent']), 'server-observed page/frame HTTP UA does not match current SDK UA')
            initial_path, initial_realm = ('/env-policy', 'document') if role == 'page' else ('/env-frame', 'frame')
            require(matches(raw, initial_realm, initial_path, native['userAgent'], ''), 'initial HTTPS document/frame request is absent or has a different SDK UA')
        workers = sample.get('workers')
        require(type(workers) is dict and type(workers.get('started')) is bool and type(workers.get('complete')) is bool and type(workers.get('cases')) is dict, 'raw Worker realm observations required')
        if label not in FULL_WORKER_LABELS:
            require(workers['started'] is False and workers['complete'] is False and workers['cases'] == {}, 'non-Worker lifecycle sample must not claim Worker observations')
            continue
        require(workers['started'] is True and workers['complete'] is True and set(workers['cases']) == set(WORKER_ROLES), 'complete actual Classic/Module/Blob/Shared/Service Worker observations required')
        for name, realm in WORKER_ROLES.items():
            row = workers['cases'][name]
            require(type(row) is dict and type(row.get('available')) is bool, 'explicit actual Worker capability required: ' + name)
            require(all(row.get(key) is False for key in ('workerCoverageVerified', 'serviceWorkerCoverageVerified', 'documentGuard', 'auditAvailable', 'protected') if key in row), 'raw Worker observation overclaims unsupported realm protection')
            relevant = [request for request in requests if request['phase'] == page['phase'] and request['documentId'] == page['documentId'] and request['realm'] in ({'service-worker', 'service-worker-install', 'service-worker-fetch'} if name == 'service' else {realm})]
            if not row['available']:
                require(name in {'shared', 'service'} and all(row.get(key) is False for key in ('created', 'executed', 'networkAllowed')) and type(row.get('reason')) is str and 0 < len(row['reason']) <= 160 and not row.get('error') and not relevant, 'unavailable Worker must have an explicit reason and cannot claim failed execution as unavailable')
                continue
            require(all(row.get(key) is True for key in ('created', 'executed', 'networkAllowed')) and ua(row.get('nativeUserAgent')) and row.get('sourceRole') == ('service-worker' if name == 'service' else realm) and not row.get('error'), 'available Worker did not really create/execute/fetch: ' + name)
            observed = clock(row.get('nativeTimeZone'))
            if not clock_matches(observed, expected_zone):
                worker_differences.append(clock_difference(observed, expected_zone, label=label, role=name))
            if row['nativeUserAgent'] != native['userAgent']:
                javascript_ua_differences.append(dict(label=label, role=name))
            require(matches(page, realm, '/worker-probe', native['userAgent']), 'actual Worker fetch HTTP UA differs from current native SDK UA: ' + name)
            if name in SCRIPT_PATHS:
                require(matches(page, 'service-worker' if name == 'service' else realm, SCRIPT_PATHS[name], native['userAgent']), 'actual Worker script request missing or UA differs: ' + name)
            if name == 'service':
                require(matches(page, 'service-worker-install', '/sw-cached', native['userAgent']), 'actual Service Worker installation fetch missing or UA differs')

    phases = {sample['page']['phase'] for sample in rows}
    require(all(request['phase'] in phases for request in requests), 'unexpected invocation phase reached controlled host')
    for request in requests:
        if request['documentId']:
            require(document_owners.get(request['documentId']) == (request['phase'], request['origin'], request['user-agent']), 'an actual request has a stale/foreign document or mismatched SDK UA')
        else:
            require(any(raw['phase'] == request['phase'] and raw['origin'] == request['origin'] and native_ua == request['user-agent'] for raw, native_ua in ((raw, sample['native']['userAgent']) for sample in rows for raw in [sample['page']] + sample['frames'])), 'an initial document request has a different phase/origin/native SDK UA')
    revisions = [sample['native']['desiredRevision'] for sample in core_rows]
    require(revisions == [revisions[0], revisions[0] + 1, revisions[0] + 1] + [revisions[0] + 2] * 6, 'actual saved timezone revisions changed unexpectedly')
    mobile_ua = samples['system']['native']['userAgent']
    require(all(sample['native']['userAgent'] == mobile_ua for sample in core_rows if sample['label'] != 'desktop') and samples['desktop']['native']['userAgent'] != mobile_ua and transitions[0]['native']['userAgent'] == samples['desktop']['native']['userAgent'] and transitions[1]['native']['userAgent'] == mobile_ua and baseline['native']['userAgent'] == mobile_ua, 'desktop/mobile native SDK UA change and restoration missing')
    proof_lifecycle(activity, samples)
    require(any(request['origin'] == samples['coop']['page']['origin'] and request['path'] == '/env-policy' and request['phase'] == 'gecko-coop' and request.get('responseCoop') == 'same-origin' for request in requests), 'host did not record writing the actual COOP response header')
    source_hashes(report, source, reader)
    result = dict(activity)
    result['_derivedWorkerTimeZoneDifferences'] = worker_differences
    result['_derivedFrameTimeZoneDifferences'] = frame_differences
    result['_derivedJavascriptUaDifferences'] = javascript_ua_differences
    result['_derivedObservationCount'] = len(rows)
    result['_derivedRfpTimeZoneObservation'] = final['page']['nativeTimeZone']
    return result


def verify_gecko_environment_policy_evidence(directory, source, expected, reader=source_bytes):
    raw = (Path(directory) / REPORT_NAME).read_bytes()
    require(0 < len(raw) <= 4 * 1024 * 1024, 'bounded report required')
    report = strict_json(raw)
    result = validate_behavior(report, source, reader)
    require(type(expected) is dict and expected.get('sourceCommit') == source and expected.get('sourceTree') == report.get('sourceTree'), 'reference source/tree mismatch')
    for installed in (report.get('expectedBuildIdentity'), result['buildIdentity']):
        require(type(installed) is dict, 'installed APK identity missing')
        for key in ('schema', 'package', 'sourceCommit', 'sourceTree', 'dirtySource', 'version', 'versionCode', 'sdkCoordinate', 'apkSha256', 'apkBytes', 'buildStampSha256', 'sdkBuildIdentity') + SDK_FIELDS:
            require(_typed_equal(installed.get(key), expected.get(key)), 'typed source/APK/SDK identity mismatch: ' + key)
        verify_installed(installed, expected)
    return dict(sourceCommit=source, sourceTree=report['sourceTree'], runNonce=report['runNonce'], integrationApkSha256=expected['apkSha256'], runId=expected['sdkBuildIdentity']['runId'], runAttempt=expected['sdkBuildIdentity']['runAttempt'], reportSha256=hashlib.sha256(raw).hexdigest(), checkCount=len(result['checks']), sampleCount=len(result['samples']), documentObservationCount=result['_derivedObservationCount'], actualAndroidExecution=True, actualGeckoExecution=True, actualPublicWebsiteExecution=False, workerCoverageVerified=False, serviceWorkerCoverageVerified=False, frameTimeZoneCoverageVerified=False, workerTimeZoneDifferences=result['_derivedWorkerTimeZoneDifferences'], frameTimeZoneDifferences=result['_derivedFrameTimeZoneDifferences'], javascriptUaDifferences=result['_derivedJavascriptUaDifferences'], rfpTimeZoneObservation=result['_derivedRfpTimeZoneObservation'], scope='Actual production Gecko first-inline primary clocks, raw frame observations, current native setting receipts, per-role controlled HTTPS UA requests and lifecycle rejection. RFP-managed clocks, frame/Worker timezone and JavaScript UA differences are observations only; no complete frame/Worker effect or public-site claim.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    expected = strict_json(args.reference.read_bytes())['eventTransport']['buildIdentity']
    result = verify_gecko_environment_policy_evidence(args.directory, args.source, expected)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
