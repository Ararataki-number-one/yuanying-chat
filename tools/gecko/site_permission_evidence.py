"""Additional controlled SDK permission evidence; never a production UI acceptance claim."""
import math
import re

ORIGIN = 'https://127.0.0.1:9877'
STAGES = ['initial', 'after-deny', 'after-default']
UNCOVERED = {'secure-context-unavailable', 'notification-api-unavailable', 'content-callback-not-observed'}


def require(value, message):
    if not value:
        raise ValueError(message)


def number(value, low, high):
    return type(value) in (int, float) and math.isfinite(value) and low <= value <= high


def permission_tap_command(value, earlier):
    require(isinstance(value, dict) and re.fullmatch('[0-9a-f]{32}', value.get('nonce', '')) is not None, 'Permission gesture nonce')
    require(len(earlier) < 3 and earlier == STAGES[:len(earlier)] and value.get('stage') == STAGES[len(earlier)], 'Permission gesture order')
    css, native = value.get('css'), value.get('native')
    require(isinstance(css, dict) and isinstance(native, dict), 'Permission gesture bounds')
    for box in (css, native):
        require(all(number(box.get(key), 1, 65536) for key in ('width', 'height')), 'Permission viewport dimensions')
        require(all(number(box.get(key), 0, 65536) for key in ('x', 'y')), 'Permission point coordinates')
    require(css['x'] < css['width'] and css['y'] < css['height'], 'Permission CSS point outside viewport')
    sx, sy = native['width'] / css['width'], native['height'] / css['height']
    require(abs(sx - sy) <= .12 * max(sx, sy), 'Permission nonuniform viewport mapping')
    x, y = round(native['x'] + css['x'] * sx), round(native['y'] + css['y'] * sy)
    require(native['x'] <= x < native['x'] + native['width'] and native['y'] <= y < native['y'] + native['height'], 'Permission native point outside viewport')
    return ['shell', 'input', 'tap', str(x), str(y)]


def verify_site_permission_evidence(report, gestures):
    require(isinstance(report, dict) and type(report.get('schema')) is int and report['schema'] == 1, 'Permission schema')
    require(report.get('scope') == 'controlled-gecko-sdk-only' and report.get('origin') == ORIGIN, 'Permission scope/origin')
    for key in ('actualAndroidExecution', 'actualGeckoExecution', 'testOnlyCertificateException'):
        require(report.get(key) is True, 'Permission actual fixture flag: ' + key)
    for key in ('productionUiAdapter', 'physicalPhoneAcceptance', 'publicNetworkTraffic'):
        require(report.get(key) is False, 'Permission unsupported acceptance claim: ' + key)
    checks = report.get('checks')
    require(isinstance(checks, list) and checks and all(isinstance(row, dict) and isinstance(row.get('name'), str) and row.get('pass') is True for row in checks), 'Permission checks')
    preflight = report.get('preflight')
    require(isinstance(preflight, dict) and re.fullmatch('[0-9a-f]{32}', preflight.get('nonce', '')) is not None, 'Permission preflight nonce')
    nonce = preflight['nonce']
    require(preflight.get('realm') == 'page-main-world' and preflight.get('url') == ORIGIN + '/pool', 'Permission preflight realm')
    require(type(preflight.get('secureContext')) is bool and type(preflight.get('notificationApi')) is bool, 'Permission API availability types')
    require(isinstance(gestures, list) and len(gestures) <= 3, 'Permission gesture count')
    for index, gesture in enumerate(gestures):
        require(isinstance(gesture, dict) and gesture.get('oneAttempt') is True and gesture.get('nonce') == nonce and gesture.get('stage') == STAGES[index], 'Permission one-shot gesture identity')
        require(gesture.get('command') == permission_tap_command(gesture.get('bounds'), STAGES[:index]), 'Permission actual gesture command')
        require(gesture['bounds']['nonce'] == nonce, 'Permission gesture bounds nonce')
    requests = report.get('requests')
    require(isinstance(requests, list) and len(requests) == len(gestures), 'Permission request/gesture correspondence')
    for index, request in enumerate(requests):
        require(isinstance(request, dict) and request.get('nonce') == nonce and request.get('stage') == STAGES[index], 'Permission request identity')
        require(request.get('realm') == 'page-main-world' and request.get('url') == ORIGIN + '/pool', 'Permission request realm')
        require(all(request.get(key) is True for key in ('secureContext', 'isTrusted', 'userActivation', 'requestCalled', 'done')), 'Permission request needs trusted main-world activation')
        require('error' not in request and request.get('result') in ('default', 'denied'), 'Permission request granted or failed')
        require(request.get('before') in ('default', 'denied') and request.get('after') in ('default', 'denied'), 'Permission page state absent or granted')
        for key in ('callbacksBefore', 'callbacksAfter'):
            require(type(request.get(key)) is int and 0 <= request[key] <= 8, 'Permission callback counter')
        require(request['callbacksAfter'] >= request['callbacksBefore'], 'Permission callback counter reversed')
    callbacks = report.get('callbacks')
    require(isinstance(callbacks, list) and len(callbacks) <= 8, 'Permission native callback bound')
    for index, callback in enumerate(callbacks):
        require(isinstance(callback, dict) and type(callback.get('sequence')) is int and callback['sequence'] == index + 1 and type(callback.get('type')) is int and callback['type'] == 1, 'Permission native callback identity')
        require(type(callback.get('value')) is int and callback['value'] in (1, 2, 3) and callback.get('origin') == ORIGIN, 'Permission native callback value/origin')
        require(callback.get('privateMode') is False and all(callback.get(key) is True for key in ('contextMatches', 'thirdPartyAbsent', 'sameSession')), 'Permission native callback namespace')
    snapshots = report.get('snapshots')
    require(isinstance(snapshots, list) and len(snapshots) <= 9, 'Permission native readback bound')
    grouped = {stage: [] for stage in ('baseline-default', 'deny', 'default')}
    order = []
    for snapshot in snapshots:
        require(isinstance(snapshot, dict) and snapshot.get('stage') in grouped, 'Permission readback stage')
        group = grouped[snapshot['stage']]
        require(type(snapshot.get('attempt')) is int and snapshot['attempt'] == len(group) + 1 <= 3, 'Permission readback attempt')
        require(type(snapshot.get('present')) is bool and type(snapshot.get('value')) is int, 'Permission readback value types')
        require(snapshot['value'] in ((1, 2, 3) if snapshot['present'] else (0,)), 'Permission missing record value')
        require(type(snapshot.get('type')) is int and snapshot['type'] == 1 and snapshot.get('origin') == ORIGIN and snapshot.get('privateMode') is False, 'Permission readback origin/type')
        require(snapshot.get('contextMatches') is True and snapshot.get('thirdPartyAbsent') is True, 'Permission readback namespace')
        group.append(snapshot);order.append(snapshot['stage'])
    require(order == sorted(order, key=lambda stage: ['baseline-default', 'deny', 'default'].index(stage)), 'Permission readback order')
    mutations = report.get('mutations')
    require(isinstance(mutations, list), 'Permission mutation list')
    if report.get('status') == 'uncovered':
        reason = report.get('reason')
        require(reason in UNCOVERED and not mutations, 'Uncovered permission case cannot mutate or hide an unknown failure')
        if reason == 'secure-context-unavailable':
            require(preflight['secureContext'] is False and not requests and not callbacks and not snapshots, 'Secure-context uncovered evidence')
        elif reason == 'notification-api-unavailable':
            require(preflight['secureContext'] is True and preflight['notificationApi'] is False and not requests and not callbacks and not snapshots, 'Notification API uncovered evidence')
        else:
            require(preflight['secureContext'] is True and preflight['notificationApi'] is True and len(requests) == 1 and not callbacks, 'Missing native callback must follow an actual completed request')
            require(grouped['baseline-default'] and not grouped['deny'] and not grouped['default'], 'Missing callback readback scope')
            baseline = grouped['baseline-default'][-1]
            require(not baseline['present'] or baseline['value'] == 3, 'Uncovered request did not start from native default')
            require(requests[0]['callbacksBefore'] == requests[0]['callbacksAfter'] == 0, 'Unobserved callback counter')
        return {'status': 'uncovered', 'reason': reason, 'actualNativePermissionChangeVerified': False, 'productionUiAdapter': False, 'physicalPhoneAcceptance': False}
    require(report.get('status') == 'passed' and preflight['secureContext'] is True and preflight['notificationApi'] is True, 'Permission evidence not passed')
    require(len(checks) >= 12 and len(requests) == len(gestures) == 3 and len(callbacks) >= 2, 'Permission completed coverage')
    require(requests[0]['callbacksBefore'] == 0 and requests[0]['callbacksAfter'] >= 1, 'Initial genuine native callback')
    require(requests[1]['before'] == requests[1]['result'] == requests[1]['after'] == 'denied' and requests[1]['callbacksAfter'] == requests[1]['callbacksBefore'] == requests[0]['callbacksAfter'], 'Stored denial did not control next request')
    require(requests[2]['before'] == 'default' and requests[2]['callbacksBefore'] == requests[1]['callbacksAfter'] and requests[2]['callbacksAfter'] == len(callbacks) > requests[2]['callbacksBefore'], 'Default behavior did not reach a fresh native callback')
    require(len(mutations) == 2, 'Exactly one deny and one default mutation')
    for mutation, stage, value, source in zip(mutations, ('deny', 'default'), (2, 3), ('content-permission-callback', 'getPermissions-readback')):
        require(isinstance(mutation, dict) and type(mutation.get('value')) is int and mutation.get('originalNativeObject') is True, 'Native mutation types')
        require(mutation == dict(stage=stage, value=value, originalNativeObject=True, source=source), 'Native mutation source/value or duplicate write')
    for stage, expected in (('baseline-default', 3), ('deny', 2), ('default', 3)):
        require(grouped[stage], 'Missing native readback: ' + stage)
        final = grouped[stage][-1]
        require(final['present'] and final['value'] == expected or not final['present'] and expected == 3, 'Native readback not confirmed: ' + stage)
    require(report.get('sameDocument') is True and report.get('draftPreserved') is True and type(report.get('sendCount')) is int and report['sendCount'] == 0, 'Permission case changed original page/draft or sent a message')
    return {'status': 'passed', 'actualNativePermissionChangeVerified': True, 'nativeMutations': 2, 'trustedPageRequests': 3, 'productionUiAdapter': False, 'physicalPhoneAcceptance': False}
