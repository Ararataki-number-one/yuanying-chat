#!/usr/bin/env python3
"""Require actual download recovery and native interaction evidence from this source."""
import argparse
import json
import pathlib
if __package__:
    from .check_connection_evidence import verify_detector_transport_evidence
else:
    from check_connection_evidence import verify_detector_transport_evidence

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
        assert pan['nativeScrollX'] > 32 and pan['pageLeft'] > 32 and pan['nativeScrollY'] > 200
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
    assert composer['top'] >= -1 and composer['bottom'] <= value['visualHeight'] + 1
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
    assert {
        'Automatic display sampling makes no requests while a reply is busy',
        'The current route gets a real first sample after the reply becomes idle',
        'Queued automatic sampling yields to a reply that started before execution',
        'Deferred automatic sampling resumes idle without a fabricated failure or route change',
        'Queued display sampling reuses a newer same-route health sample instead of probing twice',
        'Automatic telemetry deferral preserves one WebSocket and the exact core identity',
        'Actual failed-chain recovery performs exactly one full exit verification for the new entry',
        'Removing duplicate recovery verification preserves the live WebSocket and fixed exit',
    } <= {item['name'] for item in network['checks']}
    telemetry = network['telemetryScheduling']
    assert telemetry['queuedBusyRequests'] == telemetry['newerSampleDuplicateRequests'] == 0
    assert telemetry['idleSampleRequests'] > 0 and telemetry['recoveryExitRequests'] == 1
    assert telemetry['webSocketConnections'] == 1 and telemetry['webSocketEchoes'] > 0
    detector_transport = verify_detector_transport_evidence(network)
    result = {'actualAndroidExecution': True, 'actualHttpTransfer': True,
            'updateChecks': len(update['checks']), 'httpHostChecks': host['total'],
            'interactionHostChecks': interaction['total'],
            'nativeMainSerializations': checkpoint['mainSerialized'],
            'surfaceOriginSyncs': surface['originSyncs'], 'networkChecks': len(network['checks']),
            'detectorTransport': detector_transport}
    if native_fit is not None:
        result['nativeReadingFitRegression'] = native_fit
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=pathlib.Path)
    parser.add_argument('--source', required=True)
    args = parser.parse_args()
    print(json.dumps(verify_interaction_transfer_evidence(args.directory, args.source), indent=2))
