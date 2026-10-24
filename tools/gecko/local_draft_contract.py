"""F04 actual-device evidence; host controls never establish Android acceptance."""
import hashlib
import json
import math
import re
import uuid


def require(value, reason):
    if not value:
        raise ValueError('Local draft acceptance: ' + reason)


def integer(value):
    return type(value) is int and value >= 0


def digest(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def memory_snapshot(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, 'duplicate raw memory field')
            value[key] = item
        return value
    def invalid_constant(value):
        raise ValueError('Local draft acceptance: nonfinite raw memory value ' + value)
    value = json.loads(raw, object_pairs_hook=unique, parse_constant=invalid_constant)
    # A decimal overflow also becomes infinity in Python; JSONObject cannot emit it.
    json.dumps(value, allow_nan=False)
    return value


def verify_memory_adapter(phase, nonce, states):
    adapter = phase['adapter']
    source_url = 'http://127.0.0.1:8765/browser-session?context=2&localDraft=' + nonce + '#f04-saved'
    logical_url = 'https://chatgpt.com/c/f04-' + nonce
    require(type(adapter['schema']) is int and adapter['schema'] == 1
            and adapter['kind'] == 'page-memory-remember-url-only', 'memory adapter schema')
    require(adapter['sourceDomUrl'] == source_url and adapter['logicalMemoryUrl'] == logical_url,
            'memory adapter URL identity')
    require(adapter['onlyUrlAdapted'] is True and adapter['realChatGPT'] is False,
            'memory adapter scope')
    checks = adapter['checks']
    require(len(checks) == len(states), 'all actual memory calls')
    canonical = lambda value: json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    for row, (enabled, revision, draft) in zip(checks, states):
        require(row['enabled'] is enabled and integer(row['policyRevision'])
                and row['policyRevision'] == revision, 'actual memory policy')
        require(row['loopbackEntryPresent'] is False and row['storedEntryPresent'] is True,
                'memory entry admission')
        require(integer(row['loopbackSerialBefore']) and integer(row['loopbackSerialAfter'])
                and row['loopbackSerialAfter'] == row['loopbackSerialBefore']
                and integer(row['storedSerial']) and row['storedSerial'] == row['loopbackSerialBefore'] + 1,
                'actual rejected/admitted memory calls')
        require(all(isinstance(row[k], str) for k in
                    ('sourceDomRaw', 'sourceDomAfterRaw', 'memoryInputRaw', 'storedSnapshotRaw')),
                'actual raw memory inputs')
        require(row['sourceDomRaw'] == row['sourceDomAfterRaw'], 'original DOM changed')
        source = memory_snapshot(row['sourceDomRaw']); adapted = memory_snapshot(row['memoryInputRaw'])
        stored = memory_snapshot(row['storedSnapshotRaw'])
        require(type(source) is dict and type(adapted) is dict and type(stored) is dict,
                'actual nonempty memory snapshot')
        require(source['ok'] is True and source['url'] == source_url and source['draft'] == draft
                and source['draftComplete'] is True and source['hasDraft'] is True
                and integer(source['draftLength']) and source['draftLength'] == len(draft),
                'actual memory source draft')
        require(type(source['sends']) is int and source['sends'] == 0
                and source['token'] == 'synthetic-session-2' and 'f04Draft=kept' in source['cookie'],
                'actual memory source session')
        require(integer(source['history']) and type(source['scroll']) in (int, float)
                and math.isfinite(source['scroll']) and type(source['document']) in (int, float)
                and math.isfinite(source['document']) and source['document'] > 0,
                'actual memory source document')
        expected = dict(source, url=logical_url)
        require(canonical(adapted) == canonical(expected), 'memory adapter changed non-URL fields')
        expected['localDraftPolicyRevision'] = revision
        if not enabled:
            expected.update(draft=None, draftComplete=False, draftOmittedReason='local-saving-disabled')
            expected.pop('selectionStart', None); expected.pop('selectionEnd', None)
        require(canonical(stored) == canonical(expected), 'actual memory policy snapshot')


def verify_blank_barrier(phase, *, nonce=None, command=None):
    proof = phase['blankBarrier']
    fields = {'schema','kind','nonce','command','phase','uri','session',
              'requestedAtElapsedRealtime','startedAtElapsedRealtime','committedAtElapsedRealtime',
              'stoppedAtElapsedRealtime','deadlineElapsedRealtime','requestEpoch','commitEpoch',
              'completed','error','fixturePreparation','realChatGPT'}
    require(type(proof) is dict and set(proof) == fields, 'blank barrier complete receipt')
    require(type(proof['schema']) is int and proof['schema'] == 1
            and proof['kind'] == 'nonce-owned-local-blank-navigation'
            and proof['phase'] == phase['phase'] and phase['phase'] in ('off','stale-on','fresh-on'),
            'blank barrier phase')
    require(isinstance(proof['nonce'], str) and re.fullmatch('[0-9a-f]{32}', proof['nonce']) is not None
            and integer(proof['command']) and proof['command'] > 0
            and integer(proof['session']) and proof['session'] > 0, 'blank barrier owner')
    require(proof['uri'] == 'http://127.0.0.1:8765/f04-restore-blank?nonce=' + proof['nonce']
            + '&command=' + str(proof['command']) + '&phase=' + phase['phase'], 'blank barrier exact URL')
    require(proof['completed'] is True and proof['error'] == ''
            and proof['fixturePreparation'] is True and proof['realChatGPT'] is False, 'blank barrier scope/success')
    times = [proof[key] for key in ('requestedAtElapsedRealtime','startedAtElapsedRealtime',
             'committedAtElapsedRealtime','stoppedAtElapsedRealtime','deadlineElapsedRealtime')]
    require(all(integer(value) for value in times) and times == sorted(times)
            and 0 < times[-1] - times[0] <= 40000, 'blank barrier actual ordered callbacks/deadline')
    require(integer(proof['requestEpoch']) and integer(proof['commitEpoch'])
            and proof['commitEpoch'] in (proof['requestEpoch'], proof['requestEpoch'] + 1), 'blank barrier epoch')
    if nonce is not None:
        require(proof['nonce'] == nonce and proof['command'] == command, 'blank barrier invocation binding')
    return proof


def verify_local_draft_policy(report, *, device=None, source=None):
    require(type(report['schema']) is int and report['schema'] == 1, 'schema')
    require(report['forceStopBetweenPhases'] is True
            and report['automaticStartupSelectionAcceptance'] is False, 'scope')
    phases = report['phases']
    names = ['seed', 'off', 'stale-on', 'fresh-on']
    require(len(phases) == 4 and [p['phase'] for p in phases] == names, 'all four phases in order')
    common = ('actualAndroidExecution', 'actualGeckoExecution', 'fixtureOwnedStore',
              'explicitSdkRestore', 'actualGeckoSessionState', 'cookieJournalCheckpointed', 'nativeSessionCookiePresent')
    nonce = phases[0]['fixtureNonce']
    require(re.fullmatch('[0-9a-f]{32}', nonce) is not None, 'unique source form nonce')
    pids = []
    environment = phases[0]['environmentIdentity']
    require(set(environment) == {'slot','generation','environmentId'} and environment['slot'] == 1
            and type(environment['slot']) is int and integer(environment['generation'])
            and str(uuid.UUID(environment['environmentId'])) == environment['environmentId'], 'actual stable environment identity')
    for phase in phases:
        require(type(phase['schema']) is int and phase['schema'] == 1 and phase['status'] == 'passed', 'phase failure')
        require(all(phase[k] is True for k in common), 'actual execution flags')
        require(phase['automaticStartupSelectionAcceptance'] is False
                and phase['physicalPhoneAcceptance'] is False
                and phase['realChatGptPageMemoryCapture'] is False, 'scope widened')
        require(phase['profileSlot'] == 1 and type(phase['profileSlot']) is int
                and phase['fixtureNonce'] == nonce, 'environment or fixture changed')
        require(phase['environmentIdentity'] == phase['environmentIdentityAfter'] == environment,
                'environment identity/generation changed')
        require(integer(phase['pid']) and phase['pid'] > 0, 'actual process ID')
        pids.append(phase['pid'])
    require(len(set(pids)) == 4, 'each store must be read in a new Android process')
    stops = report['forceStops']
    require(len(stops) == 3 and [s['afterPhase'] for s in stops] == names[:-1], 'missing actual process stops')
    for row, pid in zip(stops, pids):
        require(row['command'] == ['shell', 'am', 'force-stop', 'local.pocketchat.test']
                and row['returnCode'] == 0 and type(row['returnCode']) is int
                and row['beforePid'] == pid and isinstance(row['stdout'], str), 'force-stop receipt')

    seed, off, stale, fresh = phases
    for phase, prefix in ((seed, 'f04-enabled-'), (stale, 'f04-fresh-')):
        capture = phase['capture']
        require(all(capture[k] is True for k in ('sourceSdkFormdataContainsUniqueDraft',
                    'sourceSdkHistoryPresent', 'sourceSdkScrollDataPresent', 'sourceSessionCookiePresent')), 'original SDK data is missing')
        require(all(digest(capture[k]) for k in ('checkpointSha256', 'payloadSha256', 'draftSha256')), 'source hashes')
        require(capture['draftSha256'] == hashlib.sha256((prefix + nonce).encode()).hexdigest(),
                'actual unique live draft differs')
        require(integer(capture['storedRevision']) and integer(capture['sourceHistory'])
                and capture['sourceHistory'] > 1 and type(capture['sends']) is int and capture['sends'] == 0, 'capture metadata')
        require(type(capture['sourceScroll']) in (float, int) and math.isfinite(capture['sourceScroll'])
                and abs(capture['sourceScroll'] - 720) <= 2, 'actual source scroll')
        require(phase['enabledPageMemoryKeepsActualDraft'] is True, 'enabled PageMemory path')
    require(seed['disabledPageMemoryRedactsActualDraft'] is True
            and seed['liveDraftPreservedAfterDisable'] is True
            and seed['disabledBeforeProcessDeath'] is True, 'disabled live-input protection')
    require(integer(seed['currentRevision']) and seed['currentRevision'] == seed['capture']['storedRevision'] + 1, 'disable revision')
    verify_memory_adapter(seed, nonce, [(True, seed['capture']['storedRevision'], 'f04-enabled-' + nonce),
                                       (False, seed['currentRevision'], 'f04-enabled-' + nonce)])
    verify_memory_adapter(stale, nonce, [(True, stale['capture']['storedRevision'], 'f04-fresh-' + nonce)])
    require('adapter' not in off and 'adapter' not in fresh, 'memory path not executed in this phase')
    require(off['disabledArchiveRejectsNewCopy'] is True
            and off['existingArchiveHistoryPreserved'] is True, 'actual archive boundary')
    require(off['enabledForStaleRead'] is True and integer(off['nextRevision']) and off['nextRevision'] == seed['currentRevision'] + 1,
            'production re-enable revision')
    for phase, capture, forms in ((off, seed['capture'], False),
                                   (stale, seed['capture'], False), (fresh, stale['capture'], True)):
        verify_blank_barrier(phase)
        read = phase['read']; restored = phase['restored']
        require(read['checkpointSha256'] == capture['checkpointSha256']
                and read['sourceSdkFormdataContainsUniqueDraft'] is True, 'cold source bytes or precondition')
        require(all(read[k] is True for k in ('allOtherSdkFieldsUnchanged', 'historyUnchanged',
                    'scrollDataUnchanged', 'freshStoreInstance')), 'SDK filtering changed other fields')
        require(read['formsPresent'] is forms and read['processId'] == phase['pid'], 'actual cold read')
        require(integer(read['storedRevision']) and read['storedRevision'] == capture['storedRevision'], 'write-time policy revision')
        wanted_revision = seed['currentRevision'] if phase is off else off['nextRevision']
        require(integer(read['currentRevision']) and read['currentRevision'] == wanted_revision
                and read['saveDraftEnabled'] is (phase is not off), 'read-time policy revision')
        require((read['storedRevision'] == read['currentRevision']) is forms, 'stale forms revived')
        require(restored['draft'] == ('f04-fresh-' + nonce if forms else '')
                and restored['sends'] == 0 and type(restored['sends']) is int, 'actual DOM draft/send result')
        require(restored['history'] == capture['sourceHistory']
                and abs(restored['scroll'] - capture['sourceScroll']) <= 2, 'actual SDK history/scroll restore')
        require(all(restored[k] is True for k in ('cookiePreserved', 'sessionCookiePreserved',
                    'sdkHistoryAndScrollRestored')), 'cookie/history/scroll restore')
        require(integer(restored['stableSamples']) and restored['stableSamples'] >= 5
                and integer(restored['stableMillis']) and 1000 <= restored['stableMillis'] <= 40000
                and type(restored['document']) in (int, float) and math.isfinite(restored['document'])
                and restored['document'] > 0, 'stable actual restored document')
    require(stale['capture']['storedRevision'] == off['nextRevision']
            and stale['capture']['checkpointSha256'] != seed['capture']['checkpointSha256'], 'fresh enabled checkpoint')
    require(fresh['ownFixtureCleaned'] is True and fresh['originalPolicyRestored'] is True, 'fixture cleanup')

    raw_bound = False
    if device is not None:
        if __package__:
            from .integration_event_contract import decode_event
        else:
            from integration_event_contract import decode_event
        require(source is not None and device['sourceCommit'] == source, 'selected source')
        identity = device['eventTransport']['buildIdentity']
        require(identity['sourceCommit'] == source, 'installed source')
        invocations = [x for x in device['eventTransport']['invocations'] if x['fixtureAction'] == 'localDraftPolicy']
        steps = [x for x in device['steps'] if x['kind'] == 'localDraftPolicy']
        require(len(invocations) == len(steps) == 4 and [x['result'] for x in steps] == phases,
                'all raw phase steps')
        require(len({x['runNonce'] for x in invocations}) == 4, 'invocation nonce reuse')
        require(nonce == invocations[0]['runNonce'], 'fixture nonce differs from actual seed invocation')
        for invocation, expected in zip(invocations, phases):
            require(invocation['processSlot'] == 1, 'invocation environment')
            accepted = []
            require(invocation['events'], 'raw invocation is empty')
            command = invocation['events'][0]['receipt']['command']
            if expected['phase'] != 'seed':
                verify_blank_barrier(expected, nonce=invocation['runNonce'], command=command)
            for index, record in enumerate(invocation['events'], 1):
                require(record['receipt']['sequence'] == index, 'raw sequence gap')
                event = decode_event(record['receipt'], record['rawUtf8'].encode('utf-8'), identity=identity,
                    nonce=invocation['runNonce'], slot=1, action='localDraftPolicy', command=command)
                require(event['kind'] != 'error', 'raw device error')
                if event['kind'] == 'localDraftPolicy':accepted.append(event['result'])
            require(accepted == [expected], 'raw result differs from selected phase')
        raw_bound = True
    return dict(phases=4, realProcessRestarts=3, rawDeviceBindingVerified=raw_bound,
                automaticStartupSelectionAcceptance=False, physicalPhoneAcceptance=False,
                pageMemoryRememberUrlAdapted=True, realChatGptPageMemoryCapture=False, realChatGPT=False)
