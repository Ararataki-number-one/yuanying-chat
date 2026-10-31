"""Consume raw owned VPN/document evidence in addition to the six legacy checks."""
import re


def verify_queued_changes46(result, source, nonce):
    def require(ok, reason):
        if not ok:
            raise ValueError('Queued changes evidence: ' + reason)

    def obj(value, reason):
        require(type(value) is dict, reason)
        return value

    def integer(value, minimum=0):
        return type(value) is int and value >= minimum

    require(type(source) is str and re.fullmatch('[0-9a-f]{40}', source) is not None, 'source')
    require(type(nonce) is str and re.fullmatch('[0-9a-f]{32}', nonce) is not None, 'current nonce')
    vpn = obj(result.get('queuedVpnLifecycle'), 'VPN report')
    observer = obj(result.get('queuedDocumentObservation'), 'document report')
    for value in (vpn, observer):
        require(value.get('sourceCommit') == source and value.get('runNonce') == nonce, 'report owner/source')
        require(value.get('processSlot') == 1 and type(value.get('processSlot')) is int, 'process slot')
        require(integer(value.get('environmentGeneration'), 1) and type(value.get('environmentId')) is str and bool(value['environmentId']), 'environment identity')
        require(integer(value.get('command'), 1), 'command')
    require(all(vpn[key] == observer[key] for key in ('environmentId', 'environmentGeneration', 'command')), 'same document environment')
    generation = vpn.get('serviceGeneration')
    require(integer(generation, 1) and type(vpn.get('originalCheckBudgetMillis')) is int and vpn['originalCheckBudgetMillis'] == 3500, 'original check budget/generation')
    require(vpn.get('actualAndroidExecution') is True and vpn.get('physicalPhoneAcceptance') is False and vpn.get('failure') == '', 'runtime scope/failure')
    require(vpn.get('appliedObserved') is True and vpn.get('closedObserved') is True, 'application/close observations')
    candidate = obj(vpn.get('expectedCandidate'), 'original DEFER save receipt')
    require(candidate.get('environmentId') == vpn['environmentId'] and type(candidate.get('generation')) is int and candidate['generation'] == vpn['environmentGeneration'], 'saved candidate environment')
    require(type(candidate.get('candidateId')) is str and re.fullmatch('[a-z0-9:-]{1,96}', candidate['candidateId']) is not None and integer(candidate.get('savedRevision'), 1), 'saved candidate/revision')
    require(type(candidate.get('appliedRevision')) is int and candidate['appliedRevision'] == 0 and candidate.get('saveState') == 'saved' and candidate.get('applicationState') == 'pending' and candidate.get('scope') == 'session', 'DEFER receipt remains pending until actual application')
    events = vpn.get('events')
    require(type(events) is list and 3 <= len(events) <= 24 and all(type(row) is dict for row in events), 'bounded event records')

    def event(kind):
        rows = [row for row in events if row.get('kind') == kind]
        require(len(rows) == 1, 'unique ' + kind)
        return obj(rows[0].get('value'), kind + ' payload')

    causal = ['full-vpn-settled', 'actual-deferred-application', 'owned-stop-dispatch', 'owned-vpn-closed-and-guard-blocked']
    indexes = []
    times = []
    for kind in causal:
        rows = [(index, row) for index, row in enumerate(events) if row.get('kind') == kind]
        require(len(rows) == 1 and integer(rows[0][1].get('at')), 'causal raw event ' + kind)
        indexes.append(rows[0][0])
        times.append(rows[0][1]['at'])
    require(indexes == sorted(indexes) and times == sorted(times), 'application precedes owned STOP and close')
    require(integer(vpn.get('beganAt')) and integer(vpn.get('stopBudgetStarted')) and vpn['beganAt'] <= vpn['stopBudgetStarted'] <= times[1] and times[-1] <= vpn['stopBudgetStarted'] + 3500, 'actual completion stays inside original check budget')

    provider_pid = None

    def ipc(value, running):
        nonlocal provider_pid
        value = obj(value, 'raw IPC')
        require(type(value.get('schema')) is int and value['schema'] == 1 and value.get('sameProcessServiceState') is True, 'IPC process provenance')
        require(integer(value.get('providerPid'), 1) and value.get('installedSource') == source, 'IPC installed identity')
        if provider_pid is None:
            provider_pid = value['providerPid']
        require(value['providerPid'] == provider_pid, 'same service/provider process')
        state = obj(value.get('state'), 'raw service state')
        require(state.get('runNonce') == nonce and state.get('sourceCommit') == source and type(state.get('generation')) is int and state['generation'] == generation, 'service owner/generation')
        require(state.get('running') is running and state.get('tunEstablished') is running and state.get('forwardsTraffic') is False, 'actual non-forwarding TUN state')
        require(state.get('mode') == 'full' and state.get('configuredRoutes') == ['0.0.0.0/0', '::/0'] and state.get('error') == '', 'full routes/service error')
        if not running:
            require(state.get('fdCloseSucceeded') is True and integer(state.get('startedAt')) and integer(state.get('stoppedAt')) and state['stoppedAt'] >= state['startedAt'], 'owned descriptor close')
            records = state.get('events')
            require(type(records) is list and len(records) <= 48 and any(type(row) is dict and type(row.get('generation')) is int and row['generation'] == generation and row.get('kind') == 'tun-closed' and row.get('detail') == 'requested-stop' for row in records), 'actual requested STOP caused descriptor close')

    def network(value, active):
        value = obj(value, 'raw CM/guard state')
        require(value.get('vpn') is active and value.get('guardVpnActive') is active, 'actual CM VPN state')
        if active:
            require(value.get('internet') is True and type(value.get('network')) is str and bool(value['network']) and value['network'] == value.get('observerNetwork'), 'live default network observation')
            require(value.get('offline') is False and value.get('connecting') is False and value.get('recoveryScheduled') is False and value.get('guardCoverageIssue') == '', 'stable full coverage')
        else:
            require(value.get('guardRequiresVpn') is True and value.get('guardAllowed') is False, 'guard blocks after real VPN removal')

    covered = event('full-vpn-settled')
    ipc(covered.get('ipc'), True)
    network(covered.get('network'), True)
    applied = event('actual-deferred-application')
    require(type(applied.get('pendingCount')) is int and applied['pendingCount'] == 0 and integer(applied.get('desiredRevision'), 1) and type(applied.get('appliedRevision')) is int and applied['appliedRevision'] == applied['desiredRevision'], 'authoritative application acknowledgement')
    require(applied['appliedRevision'] == candidate['savedRevision'], 'the same selected saved candidate applied')
    require(integer(applied.get('observedAt')) and vpn['stopBudgetStarted'] <= applied['observedAt'] <= times[1], 'actual application observation time')
    network(applied.get('network'), True)
    require(all(applied['network'].get(key) is True for key in ('guardRequiresVpn', 'guardRouteProtected', 'guardAllowed', 'networkReady')), 'verified applied route')
    require(applied['network']['network'] == covered['network']['network'], 'same actual VPN route during application')
    dispatched = event('owned-stop-dispatch')
    ipc(dispatched, True)
    require(dispatched.get('stopDispatched') is True and type(dispatched.get('stopGeneration')) is int and dispatched['stopGeneration'] == generation, 'actual owned STOP dispatch')
    closed = event('owned-vpn-closed-and-guard-blocked')
    ipc(closed.get('ipc'), False)
    # The service may close before the caller records its returned IPC receipt.
    # Owner/generation + requested-stop proves cause; clocks prove the budget.
    require(vpn['stopBudgetStarted'] <= closed['ipc']['state']['stoppedAt'] <= times[3], 'owned close remains inside this operation')
    network(closed.get('network'), False)
    admission = obj(vpn.get('originalRouteAdmission'), 'original route admission')
    require(admission.get('accepted') is True and integer(admission.get('lease'), 1), 'production begin/adopt admission')
    network(admission.get('network'), True)
    require(admission['network'].get('guardAllowed') is True and admission['network'].get('networkReady') is True, 'original explicit fixture route')

    require(observer.get('actualSdkSampling') is True and observer.get('retiredAfterApplied') is True and observer.get('productionAdmissionChanged') is False and type(observer.get('initiallyKnown')) is bool, 'actual observer scope/retirement')
    require(type(observer.get('resourceBinding')) is str and re.fullmatch('[a-zA-Z0-9-]{16,80}', observer['resourceBinding']) is not None, 'actual port binding')
    require(type(observer.get('url')) is str and re.fullmatch(r'http://127\.0\.0\.1:8765/fixture\?context=2&action=(read|seed)&command=[1-9][0-9]{0,18}', observer['url']) is not None, 'owned loopback document')
    require(integer(observer.get('navigationEpoch')), 'document epoch')
    observations = observer.get('observations')
    require(type(observations) is list and 2 <= len(observations) <= 32, 'finite busy/idle samples')
    document, sequence = None, 0
    for row in observations:
        row = obj(row, 'SDK observation')
        require(row.get('known') is True and type(row.get('busy')) is bool and type(row.get('fileBusy')) is bool and row.get('fileBusy') is False, 'actual known task observation')
        require(type(row.get('documentId')) is str and re.fullmatch('[a-zA-Z0-9-]{16,80}', row['documentId']) is not None, 'actual document identity')
        if document is None:
            document = row['documentId']
        require(row['documentId'] == document and type(row.get('navigationEpoch')) is int and row['navigationEpoch'] == observer['navigationEpoch'], 'same document/epoch')
        require(integer(row.get('sequence'), 1) and row['sequence'] > sequence, 'monotonic actual observer sequence')
        sequence = row['sequence']
    require(observations[0]['busy'] is True and observations[-1]['busy'] is False, 'actual busy-to-idle transition')
    return result
