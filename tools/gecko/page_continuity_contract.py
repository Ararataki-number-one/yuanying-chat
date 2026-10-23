"""Validate controlled page continuity evidence; source/APK binding belongs to the caller."""
import json
import re

CHECK_NAMES = (
    'Continuity starts in an actual visible Gecko document',
    'Visible readiness timeout schedules no reconnect or new document',
    'Stale readiness timeout leaves the current document epoch unchanged',
    'Busy recovery keeps admission and the current native document',
    'Busy retains actual document, unsent text, cookies and persisted task',
    'Recovery retains chooser, preparation, transfer and edit ownership 0',
    'Unavailable HEAD recovery keeps admission and the current native document',
    'Failed HEAD ran through the actual Gecko fetch probe',
    'Failed HEAD retains actual document, unsent text, cookies and persisted task',
    'Recovery retains chooser, preparation, transfer and edit ownership 1',
    'Both fault results are real failed observations, with only HEAD carrying connection timing',
    'Only the owned continuity cookie is retired',
    'Empty readiness timeout requires user retry without blocking the verified network',
)
FLAGS = ('readinessNoReload', 'busyRecoveryPreserved', 'failedProbePreserved',
         'emptyTimeoutManualOnly', 'ownedCookieCleaned', 'resourcesRestored',
         'persistedPendingRestored')
EMPTY_CONDITIONS = ('pageFailed', 'pageRecoveryErrorAvailable', 'routeAdmitted',
                    'noNetworkManualBlock', 'networkRetryStateUnchanged',
                    'noAutoReconnect', 'noAutoReload', 'pendingPreserved')
STATE_BOOLEANS = ('visible', 'navigating', 'navigationFailed', 'manualAttention',
                  'networkReady', 'guardAllowed', 'connecting', 'recoveryScheduled')
STATE_INTEGERS = ('session', 'recoveryToken', 'recoveryAttempt', 'connectionEpoch',
                  'navigationEpoch', 'loads', 'stops')
STATE_STRINGS = ('url', 'nativeUrl', 'pageError', 'status', 'networkIssue', 'pending',
                 'persistedPending')
PAGE_ERROR = '网页还未显示，请重试或检查网络'
UI_SCOPE = ('Actual ChatSession page error; visible recovery action is covered separately '
            'by production-method host tests, not an Android UI click')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value):
    return type(value) is int and 0 <= value <= 2**63 - 1


def verify_page_continuity(report):
    """Check all original assertions and independently recompute empty-timeout conditions.

    The caller must still bind the enclosing device report to its selected source,
    APK and invocation. These controlled observations do not prove a real account,
    WAN performance, or an actual Android recovery-button gesture.
    """
    require(isinstance(report, dict), 'Page continuity report is missing')
    require(type(report.get('schema')) is int and report['schema'] == 1,
            'Page continuity schema differs')
    require(report.get('status') == 'passed' and not report.get('error'),
            'Page continuity execution failed')
    require(all(report.get(key) is True for key in
                ('actualAndroidExecution', 'actualGeckoExecution') + FLAGS),
            'Original page continuity flags are incomplete')
    rows = report.get('checks')
    require(type(report.get('checkCount')) is int and report['checkCount'] == len(CHECK_NAMES)
            and isinstance(rows, list) and len(rows) == len(CHECK_NAMES),
            'All 13 original page continuity checks are required')
    require(all(isinstance(row, dict) and row.get('name') == name and row.get('pass') is True
                for row, name in zip(rows, CHECK_NAMES)),
            'Original page continuity check names, order or results differ')

    evidence = report.get('emptyConditionInputs')
    require(isinstance(evidence, dict) and evidence.get('uiScope') == UI_SCOPE,
            'Raw empty-timeout evidence or its UI scope is missing')
    require(all(evidence.get(key) is True for key in EMPTY_CONDITIONS),
            'Every empty-timeout condition must be strictly true')
    before, after = evidence.get('before'), evidence.get('after')
    for label, state in (('before', before), ('after', after)):
        require(isinstance(state, dict), 'Missing empty-timeout state: ' + label)
        require(all(type(state.get(key)) is bool for key in STATE_BOOLEANS),
                'Invalid empty-timeout boolean: ' + label)
        require(all(integer(state.get(key)) for key in STATE_INTEGERS),
                'Invalid empty-timeout integer: ' + label)
        require(all(isinstance(state.get(key), str) for key in STATE_STRINGS),
                'Invalid empty-timeout text: ' + label)
    requested = evidence.get('requestedNavigationEpoch')
    require(integer(requested) and requested == before['navigationEpoch'] + 1,
            'Empty-timeout navigation was not the single requested navigation')

    # Bind the raw empty document back to the retained actual SDK session and
    # the controlled invocation, rather than accepting a different empty session.
    snapshots = report.get('snapshots')
    require(isinstance(snapshots, list), 'Retained-page snapshots are missing')
    anchors = [row for row in snapshots
               if isinstance(row, dict) and row.get('phase') == 'after-head-failure']
    require(len(anchors) == 1, 'One retained HEAD-failure snapshot is required')
    anchor = anchors[0]
    require(integer(anchor.get('session')) and integer(anchor.get('connectionEpoch'))
            and anchor['session'] == before['session']
            and anchor['connectionEpoch'] == before['connectionEpoch'],
            'Empty-timeout state belongs to a different retained session or connection')
    require(isinstance(anchor.get('document'), dict), 'Retained controlled document is missing')
    target = anchor['document'].get('url')
    match = re.fullmatch(r'http://127\.0\.0\.1:8765/browser-continuity\?command=([1-9][0-9]*)',
                         target) if isinstance(target, str) else None
    require(match is not None, 'Retained document does not belong to the controlled invocation')
    require(before['pending'] != '', 'Controlled pending task is missing')
    try:
        pending = json.loads(before['pending'])
    except (ValueError, TypeError):
        raise ValueError('Controlled pending task is invalid') from None
    require(isinstance(pending, dict) and pending.get('attempted') is True and pending == {
        'id': 'continuity-' + match.group(1), 'kind': 'web', 'engine': 'gecko',
        'expectedUrl': 'https://chatgpt.com/', 'confirmedUrl': 'https://chatgpt.com/',
        'prompt': 'controlled task', 'attempted': True,
    }, 'Pending task belongs to a different controlled invocation')

    observed = {
        'pageFailed': after['navigationFailed'] and not after['navigating'],
        'pageRecoveryErrorAvailable': after['pageError'] == PAGE_ERROR == after['status'],
        'routeAdmitted': all(state[key] for state in (before, after)
                             for key in ('networkReady', 'guardAllowed')),
        'noNetworkManualBlock': not before['manualAttention'] and not after['manualAttention'],
        'networkRetryStateUnchanged': all(before[key] == after[key] for key in
                                         ('recoveryToken', 'recoveryAttempt', 'networkIssue', 'connectionEpoch')),
        'noAutoReconnect': all(not state[key] for state in (before, after)
                               for key in ('recoveryScheduled', 'connecting')),
        'noAutoReload': before['session'] == after['session']
            and all(state[key] == 'about:blank' for state in (before, after) for key in ('url', 'nativeUrl'))
            and not before['visible'] and not after['visible']
            and after['navigationEpoch'] == requested
            and before['loads'] == after['loads'] and before['stops'] == after['stops'],
        'pendingPreserved': before['pending'] == before['persistedPending']
            == after['pending'] == after['persistedPending'],
    }
    for key in EMPTY_CONDITIONS:
        require(observed[key] is True, 'Raw empty-timeout state contradicts condition: ' + key)
    return {'checks': len(CHECK_NAMES), 'emptyConditions': len(EMPTY_CONDITIONS)}
