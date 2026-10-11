#!/usr/bin/env python3
"""Require actual download recovery and native interaction evidence from this source."""
import argparse
import json
import pathlib

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
}


def verify_interaction_transfer_evidence(directory, source):
    directory = pathlib.Path(directory)

    def android(name):
        report = json.loads((directory / name).read_text())
        assert report['status'] == 'passed' and report['sourceCommit'] == source, name
        assert report['actualAndroidExecution'], name
        return report

    update = android('update-transfer-results.json')
    assert update['actualHttpTransfer'] and update['actualJobSchedulerExecution']
    assert len(update['checks']) >= len(UPDATE_CHECKS) and all(item['pass'] for item in update['checks'])
    assert UPDATE_CHECKS <= {item['name'] for item in update['checks']}
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
    surface = device['nativeSurfacePerformance']
    assert surface['actualGestureCount'] == 3 and surface['originChecks'] >= 20
    assert surface['originSyncs'] == 1 and surface['movedSurfaceSyncs'] > 0 and surface['typedCharacters'] > 0
    assert all(surface[key] for key in ('stationaryGeometryDeduplicated', 'initialSurfaceMoveSynced',
                                      'movedSurfaceAcceptsRealInput', 'documentAndDraftPreserved'))
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
    assert network['actualMihomoExecution'] and len(network['checks']) >= 134
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
    return {'actualAndroidExecution': True, 'actualHttpTransfer': True,
            'updateChecks': len(update['checks']), 'httpHostChecks': host['total'],
            'interactionHostChecks': interaction['total'],
            'nativeMainSerializations': checkpoint['mainSerialized'],
            'surfaceOriginSyncs': surface['originSyncs'], 'networkChecks': len(network['checks'])}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=pathlib.Path)
    parser.add_argument('--source', required=True)
    args = parser.parse_args()
    print(json.dumps(verify_interaction_transfer_evidence(args.directory, args.source), indent=2))
