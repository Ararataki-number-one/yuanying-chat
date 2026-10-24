#!/usr/bin/env python3
"""Require actual download recovery and native interaction evidence from this source."""
import argparse
import json
import pathlib
import math
if __package__:
    from .local_draft_contract import verify_local_draft_policy
else:
    from local_draft_contract import verify_local_draft_policy
if __package__:
    from .check_connection_evidence import verify_detector_transport_evidence
    from .download_resume_contract import verify_download_resume, verify_download_resume_invocation
else:
    from check_connection_evidence import verify_detector_transport_evidence
    from download_resume_contract import verify_download_resume, verify_download_resume_invocation

def verify_display_sampling(network):
    assert network['actualMihomoExecution'] is True
    assert all(item['pass'] is True for item in network['checks'])
    assert {
        'Automatic display sampling measures the current route while a reply is busy',
        'A fresh busy-route sample is reused after the reply becomes idle',
        'Queued automatic sampling measures without interrupting the newly busy reply',
        'The queued busy sample remains fresh when the reply becomes idle',
        'Queued display sampling reuses a newer same-route health sample instead of probing twice',
        'Automatic telemetry scheduling preserves one WebSocket and the exact core identity',
        'Actual failed-chain recovery performs exactly one full exit verification for the new entry',
        'Removing duplicate recovery verification preserves the live WebSocket and fixed exit',
    } <= {item['name'] for item in network['checks']}
    telemetry = network['telemetryScheduling']
    initial=network['initialDisplaySampling']
    assert all(type(initial[key]) is int for key in ('busyRequests','idleRequests'))
    assert all(type(telemetry[key]) is int for key in ('queuedBusyRequests','idleSampleRequests','newerSampleDuplicateRequests','recoveryExitRequests','webSocketConnections','webSocketEchoes'))
    assert initial['busyRequests'] == initial['idleRequests'] == 2
    assert telemetry['queuedBusyRequests'] == telemetry['idleSampleRequests'] == 2
    assert telemetry['newerSampleDuplicateRequests'] == 0
    assert telemetry['recoveryExitRequests'] == 1
    assert telemetry['webSocketConnections'] == 1 and telemetry['webSocketEchoes'] > 0
    verify_read_model_freshness(network)
    verify_read_model_identity(network)

READ_MODEL_CASES = (
    ('fresh', 1000000, 1000000, True, '正常', True),
    ('age44999', 1000000, 955001, True, '正常', True),
    ('age45000', 1000000, 955000, True, '状态待核实', False),
    ('missing-time', 10000, None, True, '状态待核实', False),
    ('zero-time', 10000, 0, True, '状态待核实', False),
    ('not-live', 1000000, 1000000, False, '未运行', False),
    ('wrong-uuid', 1000000, 1000000, True, '状态待核实', False),
    ('wrong-generation', 1000000, 1000000, True, '状态待核实', False),
    ('future59999', 1000000, 1059999, True, '正常', True),
    ('future60000', 1000000, 1060000, True, '正常', True),
    ('future60001', 1000000, 1060001, True, '状态待核实', False),
    ('fresh-reported-issue', 1000000, 1000000, True, '需检查', False),
    ('fresh-blocked-exit', 1000000, 1000000, True, '出口异常', False),
    ('stale-reported-issue', 1000000, 955000, True, '状态待核实', False),
)

def verify_read_model_freshness(network):
    """Controlled Android constructor projections, not IPC or measured latency."""
    names = {item['name'] for item in network['checks'] if item['pass'] is True}
    assert {'Android read-model freshness ' + case[0] for case in READ_MODEL_CASES} <= names
    report = network['networkReadModelFreshness']
    assert type(report['schema']) is int and report['schema'] == 1
    assert report['scope'] == 'controlled Android read-model projection; no IPC ownership, live route or real latency claim'
    row = dict(slot=0, name='controlled read model', environmentId='controlled-model-environment', generation=2)
    assert report['row'] == row
    assert all(type(report['row'][key]) is type(value) for key, value in row.items())
    assert len(report['cases']) == len(READ_MODEL_CASES)
    summary={key:value for key,value in report.items() if key!='cases'}
    checks={check['name']:check for check in network['checks']}
    for actual, (name, now, at, live, state, connected) in zip(report['cases'], READ_MODEL_CASES):
        assert actual['case'] == name and type(actual['now']) is int and actual['now'] == now
        assert actual['live'] is live and actual['connected'] is connected and actual['state'] == state
        expected = dict(environmentId=row['environmentId'], generation=2, mode='external', configured=True,
                        connected=True, route='controlled-route', delayRoute='controlled-route', delay=42,
                        delayAt=now, delayKind='response', latencyRemaining=120000, ip='192.0.2.42')
        if at is not None: expected['at'] = at
        if name == 'wrong-uuid': expected['environmentId'] = 'another-environment'
        if name == 'wrong-generation': expected['generation'] = 3
        if name.endswith('reported-issue'): expected['issue'] = 'controlled reported issue'
        if name == 'fresh-blocked-exit': expected['blocked'] = True
        assert actual['input'] == expected and actual['inputUnchanged'] is True
        assert all(type(actual['input'][key]) is type(value) for key, value in expected.items())
        assert type(actual['latency']) is str and type(actual['mainline']) is str
        same_identity=name not in ('wrong-uuid','wrong-generation')
        if same_identity: assert actual['latency'] == ('42 ms' if connected else '42 ms（上次）')
        else: assert actual['latency'] == '延迟未测' and actual['mainline'] == '地区未标注 · IP 未核验 · 延迟未测'
        timer = '（02:00）' if connected or name == 'fresh-reported-issue' else '（等待连接）'
        assert actual['timer'] == timer
        if same_identity: assert (' · 192.0.2.42 · ' if connected else ' · 上次 192.0.2.42 · ') in actual['mainline']
        check=checks['Android read-model freshness '+name]
        assert check['readModel']==actual and check['readModelSummary']==summary
    return dict(controlledAndroidProjection=True, cases=len(READ_MODEL_CASES), realLatencyMeasurement=False)

READ_MODEL_IDENTITY_CASES = ('fresh','stale','missing-time','not-live','foreign-uuid','foreign-generation',
    'missing-id','missing-generation','empty-id','string-generation','fractional-generation','overflow-generation',
    'nested-foreign-uuid','nested-string-generation')

def identity_projection_fixture(name):
    """Fixed counterfeit/parser inputs; these constants never qualify a device run."""
    import copy
    import hashlib
    assert name in READ_MODEL_IDENTITY_CASES
    row=dict(slot=0,name='controlled identity model',environmentId='controlled-identity-environment',generation=2)
    config=dict(subscriptionUrl='https://identity-model.invalid/subscription',subscriptionName='Saved subscription',
        exitHost='192.0.2.9',exitPort=1080,entry='Saved entry',entryMode='manual',exitRegion='Saved region')
    exit_id=hashlib.sha256(b'192.0.2.9:1080::').hexdigest();subscription=hashlib.sha256(config['subscriptionUrl'].encode()).hexdigest()
    observed=dict(environmentId=row['environmentId'],generation=2,mode='internal',configurationFingerprint='controlled-fingerprint',
        entryMode='latency',subscriptionName='Observed subscription',exitRegion='Observed region',exitId=exit_id,subscriptionId=subscription)
    runtime=dict(environmentId=row['environmentId'],generation=2,runningConfiguration=observed,at=1000000,mode='internal',
        configured=True,connected=True,uiLive=True,exitId=exit_id,subscriptionId=subscription,ip='192.0.2.42',observedIp='192.0.2.99',
        entry='Observed entry',delayEntry='Observed entry',delay=42,delayAt=1000000,delayKind='response',latencyRemaining=120000,
        healthDelay=20,healthDelayAt=1000000)
    if name=='stale':runtime['at']=955000
    if name=='missing-time':del runtime['at']
    if name=='foreign-uuid':runtime['environmentId']='foreign-environment'
    if name=='foreign-generation':runtime['generation']=3
    if name=='missing-id':del runtime['environmentId']
    if name=='missing-generation':del runtime['generation']
    if name=='empty-id':runtime['environmentId']=''
    if name=='string-generation':runtime['generation']='2'
    if name=='fractional-generation':runtime['generation']=2.5
    if name=='overflow-generation':runtime['generation']=2147483648
    if name=='nested-foreign-uuid':observed['environmentId']='foreign-environment'
    if name=='nested-string-generation':observed['generation']='2'
    foreign=name not in ('fresh','stale','missing-time','not-live') and not name.startswith('nested-')
    if foreign:runtime.update(configured=False,mode='external',healthDelay=-1,blocked=True,issue='foreign issue',latencyMeasuring=True)
    live=name!='not-live';connected=not foreign and name not in ('stale','missing-time') and live
    keep_observed=not foreign and not name.startswith('nested-');view={} if foreign else copy.deepcopy(runtime)
    if name.startswith('nested-'):del view['runningConfiguration']
    output=dict(state='正常' if connected else '未运行' if not live else '状态待核实',connected=connected,internal=True,
        ip='' if foreign else '192.0.2.42',region='Observed region' if keep_observed else 'Saved region',
        entry='Saved entry' if foreign else 'Observed entry',entryMode='自动优选' if keep_observed else '手动指定',
        subscription='Observed subscription' if keep_observed else 'Saved subscription',
        latency='延迟未测' if foreign else '42 ms' if connected else '42 ms（上次）',timer='（02:00）' if connected else '（等待连接）',runtime=view)
    summary=dict(schema=1,scope='controlled Android identity read-model projection; no IPC ownership, live route or real latency claim',row=row,config=config)
    return summary,dict(case=name,now=1000000,live=live,input=runtime,output=output,inputUnchanged=True)

def verify_read_model_identity(network):
    """Replay all fixed Android projections, retaining original raw input/output."""
    def exact(left,right):
        if type(left) is not type(right):return False
        if isinstance(left,dict):return left.keys()==right.keys() and all(exact(left[key],right[key])for key in left)
        if isinstance(left,list):return len(left)==len(right) and all(exact(a,b)for a,b in zip(left,right))
        return left==right
    report=network['networkReadModelIdentity'];summary={key:value for key,value in report.items()if key!='cases'}
    assert exact(summary,identity_projection_fixture('fresh')[0])
    cases=report['cases'];assert type(cases) is list and len(cases)==len(READ_MODEL_IDENTITY_CASES)
    checks=[check for check in network['checks']if check['name'].startswith('Android read-model identity ')]
    assert len(checks)==len(READ_MODEL_IDENTITY_CASES)
    for check,actual,name in zip(checks,cases,READ_MODEL_IDENTITY_CASES):
        assert check['name']=='Android read-model identity '+name and check['pass'] is True
        assert exact(actual,identity_projection_fixture(name)[1])
        assert exact(check['readModel'],actual) and exact(check['readModelSummary'],summary)
    return dict(controlledAndroidIdentityProjection=True,cases=len(cases),realLatencyMeasurement=False)

UPDATE_CHECKS = {
    'disconnectPreservesPartial', 'rangeOnlyRemaining', 'ifRangeValidator',
    'resumedShaSigner', 'singleFinalApk', 'pauseKeepsPartial',
    'activityRecreationKeepsPartial', 'processRestartKeepsPartial',
    'restartResumeRange', 'restartResumeComplete', 'streamingStatusReadable',
    'mainThreadStatusNoIo', 'actualPauseTouch', 'actualResumeTouch',
    'progressKeepsViewIdentity', 'ignoredRangeRestartsCleanly',
    'invalidContentRangeRejected', 'changedETagRejected', 'shortLengthRejected',
    'oversizeRejected', 'badHashRejected', 'badSignerRejected',
    'chatResponsiveDuringTransfer',
    'queuedResumeCannotOverridePause', 'delayedPreparationKeepsPause',
    'queuedResumeCannotOverrideCancel',
    'cancelledPartialClearedAfterProcessDeath',
    'freshDownloadAfterKilledCancellation',
}

PACKAGE_DELETE_CHECKS = {
    'readyDeletionConfirmationRetainsPackage', 'staleReadyDeletionRejected',
    'confirmedReadyPackageRemoved', 'deletionCancelsQueuedVerification',
    'readyDeletionPreservesPreferences', 'deletedReleaseDoesNotAutoDownload',
    'packageDeletionStatusNoIo', 'explicitRedownloadAfterPackageDeletion',
}

DOWNLOAD_LIST_CHECKS = {
    'Re-indexing an unchanged saved file preserves its recorded download timestamp',
    'An unchanged task sync retains its original progress heartbeat and exact shared row',
    'A changed progress sync updates only that task with new bytes and a real heartbeat',
    'A legacy history row without a time cannot move or replace an existing saved download',
    'The attached Android download list keeps actual active tasks first',
    'Completed Android cards follow actual newest-to-oldest saved times',
    'Rendered saved card displays its existing recorded download date',
    'Live byte polls retain the exact Android decor scroll card and focus',
    'The same Android progress bar reports current bytes without duplicate rows',
    'Progress-only refresh keeps the existing visible scroll offset',
    'Old downloads with no timestamp disclose the missing time rather than use today',
}


def verify_saved_file_deletion(report):
    assert report['schema'] == 1 and report['status'] == 'passed'
    assert all(report[key] is True for key in ('actualAndroidExecution',
        'actualMediaStoreExecution', 'actualPrivateProviderExecution',
        'actualWorkerThreadDeletion', 'actualSameUriPublicationBarrier',
        'staleDeleteWaitedForWriter', 'newPublishedBytesPreserved',
        'ownSyntheticDestinationsCleaned', 'lateOldSlotSuppressed',
        'actualAndroidDownloadViewExecution', 'stableDownloadRows',
        'liveProgressFocusPreserved', 'realDownloadTimeOrdering'))
    assert report['actualAdbTouchExecution'] is False and report['profileSlot'] == 7
    assert report['writerProfileSlot'] == 0 and report['oldSelectionProfileSlot'] == 7
    assert report['checkCount'] == len(report['checks']) >= 31
    assert all(item['pass'] is True for item in report['checks'])
    assert DOWNLOAD_LIST_CHECKS <= {item['name'] for item in report['checks']}
    assert report['freedMediaStoreBytes'] == 5127 and report['freedPrivateBytes'] == 8197
    assert all(report[key] == 0 for key in ('alreadyAbsentPrivateFreedBytes',
        'alreadyAbsentMediaStoreFreedBytes', 'staleMenuFreedBytes'))
    if 'downloadResume' in report:
        verify_download_resume(report['downloadResume'])
    return {'actualAndroidExecution': True, 'checks': report['checkCount'],
            'mediaStoreBytesRemoved': report['freedMediaStoreBytes'],
            'privateBytesRemoved': report['freedPrivateBytes'],
            'sameUriPublicationProtected': True, 'stableDownloadRows': True,
            'realDownloadTimeOrdering': True}


def verify_paint_case(result, cancelled=False):
    """Require actual current-command callbacks, never a prior page's counters."""
    case = result['paintCase']
    assert type(case['schema']) is int and case['schema'] == 1 and type(case['serial']) is int and case['serial'] > 0
    expected = 'http://127.0.0.1:8765/browser-loading?command=' + str(case['serial'])
    assert case['target'] == case['currentUrl'] == case['committedTarget'] == expected
    assert case['currentCase'] is True and case['committed'] is True
    assert type(case['nativeSession']) is int and case['nativeSession'] != 0
    assert type(case['currentNativeSession']) is int and case['nativeSession'] == case['currentNativeSession']
    assert all(type(case[key]) is int for key in ('requested', 'started', 'visible', 'finished'))
    assert 0 < case['requested'] <= case['started'] <= case['visible']
    if cancelled:
        assert result['cancelledBeforeFinish'] is True and type(result['finishedBeforeCancel']) is int and result['finishedBeforeCancel'] == 0
        assert case['finished'] == 0 or case['finished'] >= case['visible']
        assert result['documentReadyBeforeStop'] is True and result['visibleDocumentRetained'] is True
        assert result['reportedFailure'] is False and not result['pageError']
    else:
        assert result['firstPaintBeforeComplete'] is True and case['finished'] - case['visible'] > 500
        assert all(result[key] == case[key] for key in ('started', 'visible', 'finished'))
    return case


def verify_reading_bounds(report):
    """Check measured native geometry, never substitute page-visible DPR."""
    assert report['schema'] == 1 and report['productionDelegateRestored'] is True and report['privacyRestored'] is True
    cases = report['cases']
    assert len(cases) == 2 and [item['privacyLevel'] for item in cases] == [0, 2]

    def fit(value):
        assert value['nativeWidth'] > 0 and value['viewport'] > 0 and value['matrixScale'] > 0
        assert abs(value['matrixScale'] - value['matrixScaleY']) < .001
        assert abs(value['nativeWidth'] - value['matrixScale'] * value['layout'] * value['viewport']) < 6
        assert abs(value['choice'] - 1) < .001 and abs(value['scale'] - 1) < .02
        assert all(abs(value[key]) <= 1 for key in ('nativeScrollX', 'scrollX', 'pageLeft', 'offsetLeft'))
        assert value['scrollWidth'] <= value['viewport'] + 1
        assert len(value['blocks']) == 3
        for block in value['blocks']:
            assert value['offsetLeft'] - 1 <= block['left'] < block['right'] <= value['offsetLeft'] + value['visualWidth'] + 1
        assert value['sends'] == 0 and value['nativeUpdates'] > 0

    for case in cases:
        assert all(case[key] is True for key in ('actualGeckoExecution', 'protectionAcknowledged', 'fitUsedProductionController'))
        assert case['fingerprintingProtected'] is (case['privacyLevel'] == 2)
        assert case['stableSamples'] >= 5 and case['stableMillis'] >= 500
        before, pan, after = (case[key] for key in ('before', 'pan', 'after'))
        assert all(value['privacyLevel'] == case['privacyLevel'] and value['fingerprintingProtected'] is case['fingerprintingProtected']
                   for value in (before, pan, after))
        assert abs(before['choice'] - 4.2) < .001
        assert abs(before['matrixScale'] * before['layout'] * before['viewport'] / before['nativeWidth'] - 4.2) < .05
        assert abs(pan['nativeScrollX'] - 48) <= 1 and abs(pan['pageLeft'] - 48) <= 1 and abs(pan['nativeScrollY'] - 320) <= 1
        assert abs(after['nativeScrollY'] - pan['nativeScrollY']) <= 1
        assert 'readingBounds=controlled-fixture' in before['cookie']
        for key in ('document', 'draft', 'cookie', 'bodyHash', 'sessionIdentity', 'surfaceIdentity', 'activityIdentity'):
            assert len({value[key] for value in (before, pan, after)}) == 1, key
        assert after['draft'] == 'Unsent draft stays here'
        assert after['codeScrollWidth'] > after['codeWidth'] and after['codeLeft'] > 0
        fit(after)
    reference = cases[-1]['after']
    assert [item['phase'] for item in report['rotation']] == ['landscape', 'portrait']
    for item in report['rotation']:
        value, geometry = item['measurement'], item['geometry']
        assert value['privacyLevel'] == 2 and value['fingerprintingProtected'] is True
        fit(value)
        for key in ('document', 'draft', 'cookie', 'bodyHash', 'sessionIdentity', 'surfaceIdentity', 'activityIdentity'):
            assert value[key] == reference[key], key
        assert geometry['statusBarsVisible'] and geometry['navigationBarsVisible'] and not geometry['imeVisible']
        assert (geometry['webWidth'] > geometry['webHeight']) is (item['phase'] == 'landscape')
    keyboard = report['input']
    assert keyboard['imeVisible'] and keyboard['imeBottom'] > 0
    assert all(keyboard[key] is True for key in ('sameDocument', 'sameCookie', 'draftPreserved'))
    value = keyboard['measurement']
    assert value['privacyLevel'] == 2 and value['fingerprintingProtected'] is True
    fit(value)
    assert value['focused'] == 'composer' and 'native-input-ok' in value['draft']
    composer = value['blocks'][2]
    offset = value.get('offsetTop', 0)
    assert composer['top'] >= offset - 1 and composer['bottom'] <= offset + value['visualHeight'] + 1
    if 'nativeComposerFits' in value:
        assert value['nativeComposerFits'] is True and value['productionKeyboardController'] is True
        assert value['nativeFocusRequests'] > 0
        assert value['nativeFocusMeasurements'] > 0
        assert isinstance(value['nativeFocusWasClipped'], bool)
        assert isinstance(value['nativeFocusScrolls'], int) and value['nativeFocusScrolls'] >= 0
        assert math.isfinite(value['nativeFocusScrollDeltaCss'])
        if value['nativeFocusWasClipped']:
            assert value['nativeFocusScrolls'] > 0 and abs(value['nativeFocusScrollDeltaCss']) > 0
        window = value['windowBounds']
        assert all(math.isfinite(window[key]) for key in ('left', 'top', 'right', 'bottom'))
        assert window['bottom'] > window['top'] and window['right'] > window['left']
        assert value['imeTopPixels'] == window['bottom'] - keyboard['imeBottom']
        matrix = value['pageToSurfaceMatrix']
        assert len(matrix) == 9 and all(math.isfinite(number) for number in matrix)
        assert abs(matrix[0] - value['matrixScale']) < .001 and abs(matrix[4] - value['matrixScaleY']) < .001
        physical, visible = value['composerPhysicalRect'], value['visibleSurfaceRect']
        assert all(math.isfinite(rect[key]) for rect in (physical, visible) for key in ('left', 'top', 'right', 'bottom'))
        assert physical['right'] > physical['left'] and physical['bottom'] > physical['top']
        assert visible['left'] - 2 <= physical['left'] < physical['right'] <= visible['right'] + 2
        assert visible['top'] - 2 <= physical['top'] < physical['bottom'] <= visible['bottom'] + 2
        assert visible['bottom'] <= value['imeTopPixels'] + 2
    assert value['document'] == reference['document'] and value['cookie'] == reference['cookie']
    assert value['bodyHash'] == reference['bodyHash'] and value['sessionIdentity'] == reference['sessionIdentity']
    assert value['surfaceIdentity'] == reference['surfaceIdentity'] and value['activityIdentity'] == reference['activityIdentity']
    assert value['draft'].replace('native-input-ok', '', 1) == reference['draft']
    return {'nativeFitCases': len(cases), 'actualRotationCases': len(report['rotation']), 'actualImeFit': True}


def verify_interaction_transfer_evidence(directory, source):
    directory = pathlib.Path(directory)

    def android(name):
        report = json.loads((directory / name).read_text())
        assert report['status'] == 'passed' and report['sourceCommit'] == source, name
        assert report['actualAndroidExecution'], name
        assert report.get('diagnosticOnly', False) is False, 'Diagnostic subsets cannot replace release acceptance: ' + name
        return report

    gecko = android('gecko-performance-results.json')
    assert gecko['inputDiagnosticsEnabled'] is False
    assert gecko.get('inputNativeDiagnosticsEnabled', False) is False, 'Buffered native diagnostics cannot replace normal acceptance.'
    assert gecko['actualNativeInputTrace'] == [] and gecko['actualInputEvaluationTrace'] == []
    assert not any(item['type'] == 'selectionchange' or item['type'].startswith('script')
                   for item in gecko['actualTrustedInputEvents'])
    assert gecko['actualInputImeSettled'] and gecko['actualSingleInputBurst']
    assert {
        'Actual Android input waits for visible IME and unchanged viewport, composer and caret',
        'The single Android input burst delivers exact ordered trusted keys and real input events',
    } <= {item['name'] for item in gecko['checks'] if item['pass']}
    inputs = gecko['actualAndroidTextInputs']
    assert len(inputs) == 1
    request = inputs[0]
    assert request['text'] == '-user-typed' and request['imeVisible'] and request['imeBottom'] > 0
    assert request['stableFocusSamples'] >= 3 and request['settledMs'] >= 600
    assert request['start'] == request['end'] and 0 <= request['start'] <= len(request['draft'])
    events = gecko['actualTrustedInputEvents']
    typed = [item for item in events if item['type'] in ('keydown', 'keyup', 'beforeinput', 'input')]
    assert typed and all(item['trusted'] for item in typed) and any(item['type'] == 'input' for item in typed)
    assert ''.join(item['key'] for item in typed if item['type'] == 'keydown' and len(item['key']) == 1) == request['text']
    assert any(item['imeVisible'] and item['imeBottom'] > 0 and item['stableFocusSamples'] >= 3
               and item['settledMs'] >= 600 and item['draft'] == request['draft']
               for item in gecko['actualInputReadinessTrace'] if not item['requested'])

    update = android('update-transfer-results.json')
    assert update['actualHttpTransfer'] and update['actualJobSchedulerExecution']
    assert len(update['checks']) >= len(UPDATE_CHECKS) and all(item['pass'] for item in update['checks'])
    assert UPDATE_CHECKS <= {item['name'] for item in update['checks']}
    progress_samples = [item for item in update['cases']
                        if item.get('action') == 'transferInspect' and item.get('state') == 'downloading'
                        and item.get('speedSamplePairs', 0) > 0]
    assert progress_samples, 'Actual streaming speed and remaining-time evidence is required.'
    progress = progress_samples[-1]
    speed = progress['bytesPerSecond']
    assert speed > 0 and 0 < progress['received'] < progress['total']
    assert progress['remainingSeconds'] == (progress['total'] - progress['received'] + speed - 1) // speed
    assert progress['speedSampleDeltaBytes'] == progress['speedLastReceived'] - progress['speedFirstReceived'] > 0
    assert progress['speedSampleDurationMillis'] > 0 and progress['speedLastSampleNanos'] > progress['speedFirstSampleNanos']
    assert '/s' in progress['downloadDetailsText'] and '约剩' in progress['downloadDetailsText']
    gestures = update['actualAndroidGestures']
    assert len(gestures) == 2 and {item['label'] for item in gestures} == {'暂停下载', '继续下载'}
    for item in gestures:
        assert all(item[key] for key in ('actualNativeView', 'actualAndroidInput', 'enabled', 'clickable', 'windowFocused'))
        bounds = item['bounds']
        assert bounds['left'] < item['x'] < bounds['right'] and bounds['top'] < item['y'] < bounds['bottom']
    cancellation = update['cancellationProcessDeath']
    before, after = cancellation['before'], cancellation['after']
    assert before['cleanupWorkerBlocked'] and before['durableDiscardPending'] and before['discardPending']
    assert not before['writerWasActive'] and before['partialBytes'] > 0 and before['partialIdentity']
    assert before['pid'] != after['pid'] and after['state'] == 'available'
    assert not after['discardPending'] and not after['downloadRequested'] and not after['pendingTransferJob']
    assert after['partialBytes'] == 0 and not after['partialIdentity'] and not after['uri']
    host = json.loads((directory / 'update-transfer-host-results.json').read_text())
    assert host['actualHttpRequests'] and host['passed'] == host['total'] >= 28
    assert all(item['passed'] for item in host['checks']) and len(host['checks']) == host['total']
    interaction = json.loads((directory / 'interaction-host-results.json').read_text())
    assert interaction['passed'] == interaction['total'] >= 36 and len(interaction['checks']) == interaction['total']
    assert all(item['pass'] for item in interaction['checks'])
    assert {
        'First changed final capture yields during active reading without claiming completion content',
        'Idle preparation permits complete observation while the user keeps scrolling',
        'The fresh final capture contains the full latest body and late generated file',
        'Changing conversation before idle prevents stale body preparation',
        'Detached DOM is never prepared as the current final response',
        'One mutation batch visits shared ancestors once instead of once per token',
        'Interaction scheduling is read-only and preserves the login, draft and zero-send invariant',
        'An unrelated trusted button gesture performs no full-page visibility/layout walk',
        'A real send intent captures the exact draft and prior identities synchronously',
        'The coalesced resize preserves the final actual scale and viewport width',
    } <= {item['name'] for item in interaction['checks']}

    device = android('device-results.json')
    local_draft = verify_local_draft_policy(device['localDraftPolicy'], device=device, source=source)
    assert len(device['steps']) >= 78 and device['releaseMode']
    legacy = device['legacyEngineCompatibility']
    assert len(legacy) == 2 and {item['context'] for item in legacy} == {1, 2}
    for item in legacy:
        assert item['systemWebViews'] == 0
        assert all(item[key] for key in ('actualGecko', 'oldPreferencesPreserved', 'systemEngineRefused',
                                        'sameSdkSession', 'sameSurface', 'sameDocument', 'sameProtectedRoute'))
    reading = device['nativeReadingZoom']
    assert len(reading) == 4 and len({item['document'] for item in reading}) == 1
    for item, choice in zip(reading, (.8, .6, 1.3, .8)):
        assert abs(item['choice'] - choice) < .001 and abs(item['scale'] - max(1, choice)) < .05
        assert item['draft'] == 'Unsent draft stays here'
        assert abs(item['shownFontPixels'] / (18 * item['density']) - choice) < .06
    reading_ready = device['readingZoomReadiness']
    assert reading_ready['activityResumed'] and not reading_ready['browserPaused']
    assert reading_ready['stableFrames'] >= 8 and reading_ready['stableMillis'] >= 1000
    native_fit = None
    manifest_path = directory / 'manifest.json'
    if not manifest_path.is_file():
        manifest_path = directory / 'release-manifest.json'
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text())
        assert manifest['sourceCommit'] == source
        assert isinstance(manifest['versionCode'], int) and manifest['versionCode'] > 0
        if manifest['versionCode'] >= 48:
            assert 'nativeReadingBounds' in device, 'This release requires native fit, privacy, rotation and IME bounds evidence.'
        if manifest['versionCode'] >= 49:
            paint = [step['result'] for step in device['steps'] if step['kind'] == 'paint']
            cancelled = [step['result'] for step in device['steps'] if step['kind'] == 'cancelledLoad']
            assert len(paint) == len(cancelled) == 1
            first = verify_paint_case(paint[0])
            second = verify_paint_case(cancelled[0], cancelled=True)
            assert second['serial'] > first['serial'] and second['target'] != first['target']
            assert all(device['nativeCheckpointPerformance'][key] is True for key in ('readingFixtureCookieRemovedFromDom','readingFixtureCookieRemovedFromNative','otherDomCookiesPreserved','otherNativeCookiesPreserved'))
            assert device['nativeReadingBounds']['input']['measurement'].get('nativeComposerFits') is True
            assert device['nativeReadingBounds']['input']['measurement'].get('productionKeyboardController') is True
            for name, minimum in [('reading-host-results.json', 71), ('reading-focus-host-results.json', 17)]:
                host = json.loads((directory / name).read_text())
                assert host['sourceCommit'] == source and host['passed'] == host['total'] == len(host['checks']) >= minimum
                assert all(row['pass'] is True for row in host['checks'])
        if manifest['versionCode'] >= 50:
            verify_saved_file_deletion(device['savedFileDeletion'])
            assert PACKAGE_DELETE_CHECKS <= {item['name'] for item in update['checks']}
            assert len(update['checks']) >= 36
            deleted = update['readyPackageDeletion']['deleted']
            assert deleted['state'] == 'available' and not deleted['uri']
            assert deleted['finalBytes'] == deleted['partialBytes'] == deleted['finalApks'] == 0
            assert deleted['packageDeletion']['afterStoredBytes'] == 0
        if manifest['versionCode'] >= 71:
            verify_download_resume_invocation(device,source)
    if 'nativeReadingBounds' in device:
        native_fit = verify_reading_bounds(device['nativeReadingBounds'])
    held_cancel = device['appUpdates']['cancelDuringQuery']
    assert all(held_cancel[key] for key in ('actualSystemQuery', 'queryHeldAfterReturn',
                                          'queryReturnedAfterCancel', 'productionProviderCancel',
                                          'productionPollDrained', 'cleanupWorkerDrained',
                                          'systemRecordRemoved', 'sameRelease'))
    assert held_cancel['action'] == 'cancelDuringQuery' and held_cancel['ownedDownloadId'] > 0
    assert held_cancel['systemRowId'] == held_cancel['ownedDownloadId']
    assert held_cancel['generationAfterCancel'] > held_cancel['generationBeforeCancel']
    assert held_cancel['cancelledDownloadId'] == -1 and held_cancel['releaseCode'] > 0
    assert len(held_cancel['releaseSha']) == 64 and held_cancel['cursorClass']
    assert held_cancel['queriedUri'] == 'http://127.0.0.1:8765/update-wait'
    assert held_cancel['cursorStatusBeforeCancel'] in (1, 2, 4)
    assert held_cancel['cancelState'] == held_cancel['state'] == 'available'
    assert '取消' in held_cancel['message'] and held_cancel['downloadId'] == -1
    assert not held_cancel['uri'] and held_cancel['received'] == 0
    assert not held_cancel['downloadRequested'] and not held_cancel['pendingTransferJob']
    assert not held_cancel['finalFilePresent'] and held_cancel['pid'] == held_cancel['finalPid']
    surface = device['nativeSurfacePerformance']
    assert surface['actualGestureCount'] == 3 and surface['originChecks'] >= 20
    assert surface['originSyncs'] == 1 and surface['movedSurfaceSyncs'] > 0 and surface['typedCharacters'] > 0
    assert all(surface[key] for key in ('stationaryGeometryDeduplicated', 'initialSurfaceMoveSynced',
                                      'movedSurfaceAcceptsRealInput', 'documentAndDraftPreserved'))
    def stable_surface(report):
        ready = report['geometryReadiness']
        assert ready['imeHidden'] and ready['stableFrames'] >= 8 and ready['stableMillis'] >= 1000
        assert ready['systemBarsRequested'] and ready['normalBarsVisible']
        geometry = ready['geometry']
        assert geometry['statusBarsVisible'] and geometry['navigationBarsVisible'] and geometry['navigationInsets'] > 0
        assert all(geometry[side] == geometry['visibleSafe' + side.capitalize()]
                   for side in ('top', 'right', 'bottom', 'left'))
        assert report['geometryStableDuringSwipes'] and report['unchangedTouchEvents'] >= 20
        assert report['redundantTouchSyncs'] == 0 and report['firstTouchSyncs'] == 1
        assert report['firstTouchOriginCorrect'] and report['originSyncs'] == 1
    stable_surface(surface)
    stable_surface(update['chatInteraction'])
    checkpoint = device['nativeCheckpointPerformance']
    assert checkpoint['mainSerialized'] == 0 and checkpoint['firstBurstSerialized'] == 1
    assert checkpoint['firstBurstCoalesced'] == 999 and checkpoint['firstCandidate'] == 999
    assert checkpoint['lastCandidate'] == 1199 and checkpoint['latestWrites'] == 2 and checkpoint['written'] >= 5
    assert checkpoint['lastValidCandidate'] == 2002
    assert all(checkpoint[key] for key in ('validAfterNullCandidate', 'validAfterThrowingCandidate',
                                          'validAfterUtf8Oversize', 'invalidNewerKeepsValid',
                                          'continuousOffersPersisted'))
    assert checkpoint['continuousOffered'] == 200 and checkpoint['continuousWritesDuringOffers'] >= 1
    assert checkpoint['continuousLastCandidate'] == 4199 and checkpoint['continuousSerialized'] < 200
    assert checkpoint['serializeNanos'] > 0 and checkpoint['encodedBytes'] > 300000
    assert all(checkpoint[key] for key in ('mainSerializationZero', 'pendingBounded',
                                          'latestWinsDuringSerialization', 'oversizeKeepsPrevious',
                                          'independentStore', 'sdkSnapshotRestorable'))

    network = android('network-performance-results.json')
    assert network['actualMihomoExecution'] and len(network['checks']) >= 143
    assert all(item['pass'] for item in network['checks'])
    verify_display_sampling(network)
    detector_transport = verify_detector_transport_evidence(network)
    result = {'actualAndroidExecution': True, 'actualHttpTransfer': True,
            'updateChecks': len(update['checks']), 'httpHostChecks': host['total'],
            'interactionHostChecks': interaction['total'],
            'nativeMainSerializations': checkpoint['mainSerialized'],
            'surfaceOriginSyncs': surface['originSyncs'], 'networkChecks': len(network['checks']),
            'detectorTransport': detector_transport}
    result['localDraftPolicy'] = local_draft
    if native_fit is not None:
        result['nativeReadingFitRegression'] = native_fit
    if 'savedFileDeletion' in device:
        result['savedFileDeletion'] = verify_saved_file_deletion(device['savedFileDeletion'])
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=pathlib.Path)
    parser.add_argument('--source', required=True)
    args = parser.parse_args()
    print(json.dumps(verify_interaction_transfer_evidence(args.directory, args.source), indent=2))
