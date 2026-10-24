"""Synthetic verifier controls only; these objects are never Android evidence."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('source_terminal_contract', ROOT / 'tools/gecko/network_sources_contract.py')
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)
SOURCE, NONCE = 'a' * 40, 'b' * 32
ENV = '11111111-1111-4111-8111-111111111111'


def identifier(number):
    return '00000000-0000-4000-8000-' + str(number).zfill(12)


def reservation_protocol(report):
    """Coherent synthetic parser controls; never Android or physical IO evidence."""
    for index, row in enumerate(report['negativeCases']):
        e = row['terminalEvidence']; base = e['startedAtNs']; case_id = e['caseId']
        row['entrySnapshotHashValid'] = row['name'] != 'invalid-entry-snapshot-sha'
        row['exitSnapshotHashValid'] = row['name'] != 'invalid-exit-snapshot-sha'
        if 'startObservation' not in e:
            callback_id, registration_id, invocation_id, thread_id = 100+index*100, 101+index*100, 1000+index, 30+index
            root = dict(registrationId=registration_id, mode=2, callbackId=callback_id, callbackKind='restart',
                request=0, caseId=case_id, beganAtNs=base+2, endedAtNs=base+4,
                monitorHeldBefore=True, monitorHeldAfter=True, startingBefore=False, startingAfter=True,
                restartQueuedBefore=False, restartQueuedAfter=False, waitersBefore=[],waitersAfter=[callback_id],
                exactAppend=True,adapterCallbackMatches=False,rootCallbackRetained=False,
                invocationIdBefore=0,invocationIdAfter=0,workerThreadIdBefore=0,workerThreadIdAfter=0)
            worker = dict(invocationId=invocation_id,rootRegistrationId=registration_id,rootCallbackId=callback_id,
                caseId=case_id,mode=2,javaThreadId=thread_id,beganAtNs=base+5,endedAtNs=e['restartTerminal']['atNs']-2,
                waitersBefore=[callback_id],waitersAfter=[],startingBefore=True,startingAfter=False,
                restartQueuedBefore=False,restartQueuedAfter=False)
            e['startObservation'] = dict(schema=1,caseId=case_id,sourceCommit=SOURCE,runNonce=NONCE,
                rootCallbackId=callback_id,rootRegistration=root,admissions=[],workerInvocations=[worker],errors=[])
        observation=e['startObservation'];root=observation['rootRegistration'];worker=observation['workerInvocations'][0]
        owned=[copy.deepcopy(a) for a in observation['admissions'] if a['rootCallbackRetained']]
        owned_requests={a['request'] for a in owned}
        later=[]
        for number, recovery in enumerate(r for r in e['recoveries'] if r['request'] not in owned_requests):
            callback=root['callbackId']+10+number;registration=root['registrationId']+10+number
            later.append(dict(registrationId=registration,mode=1,callbackId=callback,callbackKind='recovery',
                request=recovery['request'],caseId=case_id,beganAtNs=recovery['requestedAtNs']+1,
                endedAtNs=recovery['requestedAtNs']+2,monitorHeldBefore=True,monitorHeldAfter=True,
                startingBefore=False,startingAfter=True,restartQueuedBefore=False,restartQueuedAfter=False,
                waitersBefore=[],waitersAfter=[callback],exactAppend=True,adapterCallbackMatches=True,
                rootCallbackRetained=False,invocationIdBefore=0,invocationIdAfter=0,workerThreadIdBefore=0,workerThreadIdAfter=0))
        observation['admissions']=owned+later
        owned_observation=copy.deepcopy(observation);owned_observation['admissions']=owned
        prepared_began=worker['beganAtNs']+1;prepared_end=prepared_began+1
        callback_at=e['restartTerminal']['atNs']-1;verified=e['restartTerminal']['atNs']+1
        e['reservation']=dict(schema=1,prototypeOnly=True,acceptedAsRepair=False,caseId=case_id,
            sourceCommit=SOURCE,runNonce=NONCE,beganAtNs=e['restartBeganAtNs'],deadlineNs=e['restartDeadlineAtNs'],
            budgetNs=75_000_000_000,prepared=True,preparationCount=1,delegationCount=1,originalDelegations=1,
            callbackCount=1,failed=False,state='prepared',admittedAtNs=root['beganAtNs'],
            admission=dict(atNs=e['restartBeganAtNs'],onUiThread=True,monitorHeld=True,ownerWasEmpty=True,
                starting=False,connecting=False,restartQueued=False,pendingWaiters=0),
            admissionContacts=copy.deepcopy(row['before']),actualPreparationContacts=copy.deepcopy(row['before']),
            actualContactsAfterOriginal=copy.deepcopy(row['before']),
            preparationResult=dict(managedCoreStopped=True,contacts=copy.deepcopy(row['before']),
                entrySnapshotHashValid=row['entrySnapshotHashValid'],exitSnapshotHashValid=row['exitSnapshotHashValid']),
            realRegistration=copy.deepcopy(root),invocationId=worker['invocationId'],prepareMonitorHeld=False,
            prepareThreadId=worker['javaThreadId'],originalThreadId=worker['javaThreadId'],
            prepareBeganAtNs=prepared_began,prepareEndedAtNs=prepared_end,originalBeganAtNs=prepared_end+1,
            originalEndedAtNs=worker['endedAtNs']-1,
            actualCallback=dict(ok=False,message='synthetic rejected source',atNs=callback_at,onUiThread=True,threadId=1),
            validation=dict(atNs=verified,prepared=True,preparations=1,delegations=1,callbacks=1,failed=False,
                state='prepared',scopeOwned=True,starting=False,restartQueued=False,pendingWaiters=0,
                workerCompleted=True,workerFailed=False,rootObservation=owned_observation))
    report['reservationDiagnostics']=[row['terminalEvidence'] for row in report['negativeCases']]
    return report


def synthetic_report():
    """Three cases without recovery and one real-shaped overlapping callback."""
    report = dict(sourceCommit=SOURCE, runNonce=NONCE,
        runnerInvocation=dict(sourceCommit=SOURCE, runNonce=NONCE),
        buildIdentity=dict(schema=1, sourceCommit=SOURCE, sourceTree='c' * 40,
            dirtySource=False, package='local.pocketchat.test', apkSha256='d' * 64,
            apkBytes=1000, buildStampSha256='e' * 64, version='2.0.17', versionCode=70),
        fixtureIdentity=dict(identity=dict(slot=0, generation=1, environmentId=ENV)),
        initial=dict(servicePid=99), negativeCases=[], requests=[])
    names = ['invalid-entry-snapshot-sha', 'invalid-exit-snapshot-sha',
             'same-name-changed-exit', 'same-name-changed-entry']
    for index, name in enumerate(names):
        base = (index + 1) * 100_000_000_000
        case_id = identifier(index + 1)
        contacts = dict(fixedTarget=3, decoyTarget=0, ip=2, plainProbe=4,
                        fixedAllConnected=7, decoyAllConnected=0)

        def snapshot(generation, live=False):
            return dict(slot=0, pid=50 + index if live else 0, servicePid=99,
                        state='running' if live else 'closed', alive=live,
                        generation=identifier(generation), configuration='f' * 64,
                        controllerPort=12345, proxyPort=12346, webProbePort=12347)

        def fence():
            return dict(caseId=case_id, sourceCommit=SOURCE, runNonce=NONCE,
                environmentId=ENV, environmentGeneration=1, slot=0,
                sessionIdentity=1, browserIdentity=2, transportIdentity=3,
                connectionEpoch=0, recoveryToken=0, recoveryRequestSerial=0,
                routeSerial=10, starting=False, connecting=False, ready=False,
                hasVerifiedReceipt=False)

        def stop(live_generation, closed_generation, began, ended, serial):
            live, closed = snapshot(live_generation, True), snapshot(closed_generation)
            return dict(caseId=case_id, beganAtNs=base + began, endedAtNs=base + ended,
                recoveryRequestSerial=serial, afterRequestSerial=serial, reason='START_FAILED',
                observation='client cache after original stopOwnedCore returned; not exit proof',
                owned={k:live[k] for k in ('pid', 'servicePid', 'generation', 'configuration')},
                beforeCache=live, afterCache=closed)

        closed = snapshot(100 + index)
        e = dict(schema=1, status='passed', case=name, caseId=case_id,
            sourceCommit=SOURCE, runNonce=NONCE, startedAtNs=base,
            restartBeganAtNs=base + 1, restartDeadlineAtNs=base + 1 + 75_000_000_000,
            restartTerminal=dict(ok=False, atNs=base + 100, cache=copy.deepcopy(closed)),
            fetchBudgetMs=22000, fetchBeganAtNs=base + 200,
            deadlineAtNs=base + 200 + 22_000_000_000,
            postFetchCache=dict(atNs=base + 400, cutAtNs=base + 410,
                coreAlive=False, ready=False, message='rejected synthetic candidate',
                cache=copy.deepcopy(closed), fence=fence()),
            recoveries=[], stopObservations=[], fenceBefore=fence(), fenceAfter=fence(),
            terminalAnchor=copy.deepcopy(closed),
            freshRead=dict(method='NetworkTransportClient.call(snapshot)',
                requestedAtNs=base + 600, receivedAtNs=base + 700, snapshot=copy.deepcopy(closed)),
            finalCache=copy.deepcopy(closed), completedAtNs=base + 800,
            contactsBefore=copy.deepcopy(contacts), contactsAfter=copy.deepcopy(contacts))
        if name.startswith('same-name-'):
            e['stopObservations'].append(stop(200 + index, 100 + index, 20, 50, 0))
        if name == 'same-name-changed-entry':
            terminal = fence()
            terminal.update(connectionEpoch=1, recoveryToken=1, recoveryRequestSerial=1, routeSerial=12)
            pending = dict(terminal, recoveryToken=0, starting=True, connecting=True, routeSerial=11)
            e['postFetchCache'].update(coreAlive=True, cache=snapshot(300, True), fence=pending)
            last_closed = snapshot(301)
            e['recoveries'].append(dict(request=1, caseId=case_id, recoveryToken=0,
                connectionEpoch=1, requestedAtNs=base + 350, completedAtNs=base + 550,
                outcome='FAILED', hasReceipt=False, terminalCache=copy.deepcopy(last_closed),
                terminalFence=copy.deepcopy(terminal)))
            e['stopObservations'].append(stop(300, 301, 450, 500, 1))
            e['fenceBefore'] = copy.deepcopy(terminal)
            e['fenceAfter'] = copy.deepcopy(terminal)
            e['terminalAnchor'] = copy.deepcopy(last_closed)
            e['freshRead']['snapshot'] = copy.deepcopy(last_closed)
            e['finalCache'] = copy.deepcopy(last_closed)
        request = dict(id=name, expected=False, ok=False, beganAtNs=base + 210,
                       endedAtNs=base + 390, before=copy.deepcopy(contacts), after=copy.deepcopy(contacts))
        report['requests'].append(copy.deepcopy(request))
        report['negativeCases'].append(dict(name=name, started=False, readyAfter=False,
            coreAliveAfter=False, postFetchObservedAtNs=base + 400,
            message='rejected synthetic candidate', before=copy.deepcopy(contacts),
            after=copy.deepcopy(contacts), request=request, terminalEvidence=e))
    return reservation_protocol(report)


def synthetic_joined_report():
    """One restart really owns the stop; recovery is only its second waiter."""
    report = synthetic_report()
    row = report['negativeCases'][-1]
    e = row['terminalEvidence']
    base, case_id = e['startedAtNs'], e['caseId']
    stop = e['stopObservations'][-1]
    stop.update(beganAtNs=base + 100, endedAtNs=base + 290,
                recoveryRequestSerial=0, afterRequestSerial=1)
    e['stopObservations'] = [stop]
    e['restartTerminal'].update(atNs=base + 300, cache=copy.deepcopy(e['terminalAnchor']))
    e['fetchBeganAtNs'] = base + 310
    e['deadlineAtNs'] = base + 310 + 22_000_000_000
    row['request']['beganAtNs'] = base + 320
    report['requests'][-1] = copy.deepcopy(row['request'])
    e['postFetchCache'].update(coreAlive=False, cache=copy.deepcopy(e['terminalAnchor']),
                              fence=copy.deepcopy(e['fenceBefore']))
    e['recoveries'][0].update(requestedAtNs=base + 150, completedAtNs=base + 305)
    root = dict(registrationId=1, mode=2, callbackId=10, callbackKind='restart',
        request=0, caseId=case_id, beganAtNs=base+2, endedAtNs=base+4,
        monitorHeldBefore=True, monitorHeldAfter=True, startingBefore=False,
        startingAfter=True, restartQueuedBefore=False, restartQueuedAfter=False,
        waitersBefore=[], waitersAfter=[10], exactAppend=True,
        adapterCallbackMatches=False, rootCallbackRetained=False,
        invocationIdBefore=0, invocationIdAfter=0, workerThreadIdBefore=0, workerThreadIdAfter=0)
    admission = dict(registrationId=2, mode=1, callbackId=11, callbackKind='recovery',
        request=1, caseId=case_id, beganAtNs=base+160, endedAtNs=base+170,
        monitorHeldBefore=True, monitorHeldAfter=True, startingBefore=True,
        startingAfter=True, restartQueuedBefore=False, restartQueuedAfter=False,
        waitersBefore=[10], waitersAfter=[10,11], exactAppend=True,
        adapterCallbackMatches=True, rootCallbackRetained=True,
        invocationIdBefore=20, invocationIdAfter=20, workerThreadIdBefore=30, workerThreadIdAfter=30)
    worker = dict(invocationId=20, rootRegistrationId=1, rootCallbackId=10,
        caseId=case_id, mode=2, javaThreadId=30, beganAtNs=base+5, endedAtNs=base+295,
        waitersBefore=[10], waitersAfter=[], startingBefore=True, startingAfter=False,
        restartQueuedBefore=False, restartQueuedAfter=False)
    stop['startInvocation'] = dict(invocationId=20, invocationIdAfter=20,
        rootRegistrationId=1, rootCallbackId=10, caseId=case_id,
        javaThreadId=30, javaThreadIdAfter=30, beganAtNs=base+101, endedAtNs=base+291,
        owned=copy.deepcopy(stop['owned']))
    stop['joinedRecovery'] = dict(schema=1, caseId=case_id, sourceCommit=SOURCE,
        runNonce=NONCE, request=1, registrationId=2, callbackId=11,
        rootRegistrationId=1, rootCallbackId=10, invocationId=20, javaThreadId=30,
        stopBeganAtNs=stop['beganAtNs'], stopEndedAtNs=stop['endedAtNs'],
        owned=copy.deepcopy(stop['owned']), admission=copy.deepcopy(admission))
    e['startObservation'] = dict(schema=1, caseId=case_id, sourceCommit=SOURCE,
        runNonce=NONCE, rootCallbackId=10, rootRegistration=root,
        admissions=[admission], workerInvocations=[worker], errors=[])
    e['startObservationWait'] = dict(method='actual-start-worker-observer-completion',
                                    requestedAtNs=base+420, completedAtNs=base+430)
    return reservation_protocol(report)


class SourceRouteJoinedStartContractTest(unittest.TestCase):
    def reject(self, mutate):
        value = synthetic_joined_report()
        row = value['negativeCases'][-1]
        e = row['terminalEvidence']
        mutate(value, e, e['stopObservations'][0])
        with self.assertRaises((AssertionError, KeyError, TypeError)):
            C.verify_source_route_terminal(value, SOURCE)

    def test_exact_registered_join_preserves_all_original_terminal_requirements(self):
        value = synthetic_joined_report()
        before = copy.deepcopy(value)
        self.assertEqual(C.verify_source_route_terminal(value, SOURCE)['cases'], 4)
        self.assertEqual(value, before)

    def test_count_change_without_monitor_worker_proof_still_fails(self):
        self.reject(lambda r,e,s:e.pop('startObservation'))
        self.reject(lambda r,e,s:s.pop('joinedRecovery'))
        self.reject(lambda r,e,s:s.pop('startInvocation'))

    def test_join_does_not_accept_prior_case_or_different_source_nonce(self):
        for container in ('startObservation', 'joinedRecovery'):
            for field,value in [('caseId',identifier(999)),('sourceCommit','0'*40),('runNonce','0'*32)]:
                self.reject(lambda r,e,s,c=container,f=field,v=value:(e if c=='startObservation' else s)[c].update({f:v}))

    def test_identity_booleans_cannot_masquerade_as_queue_or_worker_numbers(self):
        self.reject(lambda r,e,s:e['startObservation']['rootRegistration'].update(waitersAfter=[True]))
        self.reject(lambda r,e,s:e['startObservation']['workerInvocations'][0].update(javaThreadId=True))
        self.reject(lambda r,e,s:s['joinedRecovery']['admission'].update(mode=True))
        self.reject(lambda r,e,s:s['startInvocation']['owned'].update(pid=True))

    def test_only_actual_original_monitor_and_exact_callback_append_qualify(self):
        for field in ('monitorHeldBefore','monitorHeldAfter','exactAppend','adapterCallbackMatches',
                      'rootCallbackRetained','startingBefore','startingAfter'):
            self.reject(lambda r,e,s,f=field:e['startObservation']['admissions'][0].update({f:False}))
        self.reject(lambda r,e,s:e['startObservation']['admissions'][0].update(callbackKind='other'))
        self.reject(lambda r,e,s:e['startObservation']['admissions'][0].update(waitersAfter=[10,12]))
        self.reject(lambda r,e,s:e['startObservation']['admissions'][0].update(waitersBefore=[]))

    def test_queued_restart_carrying_original_waiter_is_not_same_operation(self):
        for which in ('rootRegistration','admissions','workerInvocations'):
            for field in ('restartQueuedBefore','restartQueuedAfter'):
                self.reject(lambda r,e,s,w=which,f=field:(e['startObservation'][w] if w=='rootRegistration' else e['startObservation'][w][0]).update({f:True}))
        self.reject(lambda r,e,s:e['startObservation']['workerInvocations'].append(copy.deepcopy(e['startObservation']['workerInvocations'][0])))
        self.reject(lambda r,e,s:e['startObservation']['admissions'].append(dict(e['startObservation']['admissions'][0],mode=2)))
        self.reject(lambda r,e,s:e['startObservation']['errors'].append('queued restart'))

    def test_same_thread_with_different_actual_invocation_rejects(self):
        for field in ('invocationIdBefore','invocationIdAfter'):
            self.reject(lambda r,e,s,f=field:e['startObservation']['admissions'][0].update({f:21}))
        self.reject(lambda r,e,s:s['startInvocation'].update(invocationIdAfter=21))
        self.reject(lambda r,e,s:e['startObservation']['workerInvocations'][0].update(invocationId=21))

    def test_join_registration_cannot_move_outside_actual_worker_or_before_request(self):
        self.reject(lambda r,e,s:e['startObservation']['admissions'][0].update(beganAtNs=e['startedAtNs']+120))
        self.reject(lambda r,e,s:e['startObservation']['admissions'][0].update(endedAtNs=e['startedAtNs']+310))
        self.reject(lambda r,e,s:e['startObservation']['workerInvocations'][0].update(endedAtNs=e['freshRead']['requestedAtNs']+1))
        self.reject(lambda r,e,s:e['recoveries'][0].update(requestedAtNs=s['beganAtNs']-1))
        self.reject(lambda r,e,s:e['recoveries'][0].update(requestedAtNs=s['endedAtNs']+1))

    def test_owned_pid_service_generation_and_raw_copy_cannot_change(self):
        for field,value in [('pid',123),('servicePid',101),('generation',identifier(999)),('configuration','0'*64)]:
            self.reject(lambda r,e,s,f=field,v=value:s['startInvocation']['owned'].update({f:v}))
            self.reject(lambda r,e,s,f=field,v=value:s['joinedRecovery']['owned'].update({f:v}))
        self.reject(lambda r,e,s:s['joinedRecovery']['admission'].update(callbackId=12))

    def test_original_final_fence_fresh_ipc_and_target_guards_remain_required(self):
        self.reject(lambda r,e,s:e.pop('fenceAfter'))
        self.reject(lambda r,e,s:e.pop('finalCache'))
        self.reject(lambda r,e,s:e['freshRead']['snapshot'].update(alive=True))
        self.reject(lambda r,e,s:e['contactsAfter'].update(fixedTarget=4))
        self.reject(lambda r,e,s:e.update(status='failed'))

    def test_two_increment_or_foreign_request_cannot_use_one_join(self):
        self.reject(lambda r,e,s:s.update(afterRequestSerial=2))
        self.reject(lambda r,e,s:e['startObservation']['admissions'][0].update(request=2))
        self.reject(lambda r,e,s:s['joinedRecovery'].update(request=2))

    def test_observer_completion_wait_is_real_bounded_and_before_only_fresh_read(self):
        self.reject(lambda r,e,s:e.pop('startObservationWait'))
        self.reject(lambda r,e,s:e['startObservationWait'].update(method='retry-until-closed'))
        self.reject(lambda r,e,s:e['startObservationWait'].update(requestedAtNs=e['recoveries'][0]['completedAtNs']-1))
        self.reject(lambda r,e,s:e['startObservationWait'].update(completedAtNs=e['freshRead']['requestedAtNs']+1))
        self.reject(lambda r,e,s:e['startObservationWait'].update(completedAtNs=e['deadlineAtNs']+1))


class SourceRouteTerminalContractTest(unittest.TestCase):
    def reject(self, mutate):
        value = synthetic_report()
        mutate(value)
        with self.assertRaises((AssertionError, KeyError, TypeError)):
            C.verify_source_route_terminal(value, SOURCE)

    def test_three_idle_cases_and_overlapping_recovery_pass_without_mutation(self):
        value = synthetic_report()
        before = copy.deepcopy(value)
        self.assertEqual(C.verify_source_route_terminal(value, SOURCE)['cases'], 4)
        self.assertEqual(value, before)
        self.assertIs(value['negativeCases'][-1]['terminalEvidence']['postFetchCache']['coreAlive'], True)
        self.assertIs(value['negativeCases'][-1]['coreAliveAfter'], False)

    def test_missing_new_structure_fails_for_old_report_shape(self):
        self.reject(lambda r:r['negativeCases'][0].pop('terminalEvidence'))
        self.reject(lambda r:r.pop('buildIdentity'))

    def test_old_cached_alive_or_unknown_boolean_is_never_terminal_success(self):
        for field in ('started', 'readyAfter', 'coreAliveAfter'):
            for value in (True, 0, 1, None, 'false'):
                with self.subTest(field=field, value=value):
                    self.reject(lambda r,f=field,v=value:r['negativeCases'][-1].update({f:v}))

    def test_wrong_source_runner_nonce_and_build_fail(self):
        for container, field, value in [('runnerInvocation','sourceCommit','0'*40),
                ('runnerInvocation','runNonce','0'*32),('buildIdentity','sourceCommit','0'*40),
                ('buildIdentity','dirtySource',True),('buildIdentity','package','local.pocketchat'),
                ('buildIdentity','apkSha256','unknown'),('buildIdentity','versionCode',True)]:
            self.reject(lambda r,c=container,f=field,v=value:r[c].update({f:v}))

    def test_wrong_case_duplicate_case_id_and_nonce_fail(self):
        for field, value in [('case','same-name-changed-exit'),('caseId',identifier(1)),
                             ('runNonce','0'*32),('sourceCommit','0'*40)]:
            self.reject(lambda r,f=field,v=value:r['negativeCases'][-1]['terminalEvidence'].update({f:v}))

    def test_restart_and_fetch_budgets_remain_exact(self):
        for field in ('restartDeadlineAtNs','deadlineAtNs'):
            self.reject(lambda r,f=field:r['negativeCases'][-1]['terminalEvidence'].__setitem__(f,
                r['negativeCases'][-1]['terminalEvidence'][f]+1))
        self.reject(lambda r:r['negativeCases'][-1]['terminalEvidence'].update(fetchBudgetMs=22001))

    def test_terminal_past_deadline_or_backward_timestamps_fail(self):
        self.reject(lambda r:r['negativeCases'][-1]['terminalEvidence'].update(completedAtNs=
            r['negativeCases'][-1]['terminalEvidence']['deadlineAtNs']+1))
        self.reject(lambda r:r['negativeCases'][-1]['terminalEvidence']['freshRead'].update(receivedAtNs=1))
        self.reject(lambda r:r['negativeCases'][-1]['terminalEvidence']['postFetchCache'].update(cutAtNs=1))

    def test_bool_cannot_impersonate_any_raw_integer(self):
        for path in [('fetchBudgetMs',),('postFetchCache','atNs'),('freshRead','requestedAtNs'),
                     ('finalCache','slot'),('finalCache','pid'),('finalCache','servicePid'),
                     ('fenceBefore','sessionIdentity')]:
            def mutate(r,path=path):
                value=r['negativeCases'][-1]['terminalEvidence']
                for field in path[:-1]:value=value[field]
                value[path[-1]]=True
            self.reject(mutate)

    def test_recovery_must_already_exist_at_selection_cut(self):
        self.reject(lambda r:r['negativeCases'][-1]['terminalEvidence']['recoveries'][0].update(
            requestedAtNs=r['negativeCases'][-1]['terminalEvidence']['postFetchCache']['cutAtNs']+1))

    def test_recovery_must_complete_before_fresh_read(self):
        self.reject(lambda r:r['negativeCases'][-1]['terminalEvidence']['recoveries'][0].update(
            completedAtNs=r['negativeCases'][-1]['terminalEvidence']['freshRead']['requestedAtNs']+1))

    def test_ready_post_fetch_cannot_be_hidden_by_a_later_closed_snapshot(self):
        self.reject(lambda r:r['negativeCases'][-1]['terminalEvidence']['postFetchCache'].update(ready=True))

    def test_live_post_fetch_needs_a_recovery_overlapping_that_actual_observation(self):
        self.reject(lambda r:r['negativeCases'][0]['terminalEvidence']['postFetchCache'].update(coreAlive=True))
        self.reject(lambda r:r['negativeCases'][-1]['terminalEvidence']['recoveries'][0].update(
            requestedAtNs=r['negativeCases'][-1]['terminalEvidence']['postFetchCache']['atNs']+1))

    def test_recovery_outcome_receipt_request_and_token_binding(self):
        for field,value in [('outcome','RECOVERED'),('hasReceipt',True),('request',2),
                            ('recoveryToken',8),('connectionEpoch',9),('caseId',identifier(1))]:
            self.reject(lambda r,f=field,v=value:r['negativeCases'][-1]['terminalEvidence']['recoveries'][0].update({f:v}))

    def test_duplicate_recovery_never_passes(self):
        self.reject(lambda r:r['negativeCases'][-1]['terminalEvidence']['recoveries'].append(
            copy.deepcopy(r['negativeCases'][-1]['terminalEvidence']['recoveries'][0])))

    def test_two_already_registered_sequential_recoveries_pass(self):
        value=synthetic_report();e=value['negativeCases'][-1]['terminalEvidence'];base=e['startedAtNs']
        second=e['recoveries'][0];first=copy.deepcopy(second)
        first.update(requestedAtNs=base+250,completedAtNs=base+300)
        first['terminalCache']['generation']=identifier(351)
        first_stop=copy.deepcopy(e['stopObservations'][-1])
        first_stop.update(beganAtNs=base+260,endedAtNs=base+280)
        first_stop['owned']['generation']=first_stop['beforeCache']['generation']=identifier(350)
        first_stop['afterCache']['generation']=identifier(351)
        second.update(request=2,recoveryToken=1,connectionEpoch=2)
        second['terminalFence'].update(connectionEpoch=2,recoveryToken=2,recoveryRequestSerial=2,routeSerial=14)
        e['postFetchCache']['fence'].update(connectionEpoch=2,recoveryToken=1,recoveryRequestSerial=2,routeSerial=13)
        e['stopObservations'][-1].update(recoveryRequestSerial=2,afterRequestSerial=2)
        e['stopObservations'].insert(1,first_stop)
        e['recoveries'].insert(0,first)
        e['fenceBefore']=copy.deepcopy(second['terminalFence'])
        e['fenceAfter']=copy.deepcopy(second['terminalFence'])
        reservation_protocol(value)  # Add matching registrations for both unchanged terminal recoveries.
        self.assertEqual(C.verify_source_route_terminal(value,SOURCE)['cases'],4)
        for change in ('token','request','order'):
            bad=copy.deepcopy(value);rows=bad['negativeCases'][-1]['terminalEvidence']['recoveries']
            if change=='token':rows[1]['recoveryToken']=0
            elif change=='request':rows[1]['request']=3
            else:rows.reverse()
            with self.subTest(change=change),self.assertRaises((AssertionError,KeyError,TypeError)):
                C.verify_source_route_terminal(bad,SOURCE)

    def test_fences_cannot_cross_case_environment_session_or_transport(self):
        for field,value in [('environmentId',identifier(999)),('environmentGeneration',2),
                            ('slot',1),('sessionIdentity',44),('transportIdentity',44),
                            ('recoveryRequestSerial',2),('starting',True),('hasVerifiedReceipt',True)]:
            self.reject(lambda r,f=field,v=value:r['negativeCases'][-1]['terminalEvidence']['fenceAfter'].update({f:v}))

    def test_owned_pid_generation_service_and_config_must_match_live_snapshot(self):
        for field,value in [('pid',999),('generation',identifier(999)),('servicePid',999),
                            ('configuration','0'*64)]:
            self.reject(lambda r,f=field,v=value:r['negativeCases'][-1]['terminalEvidence']['stopObservations'][-1]['owned'].update({f:v}))

    def test_stop_must_close_change_generation_and_keep_service_identity(self):
        for field,value in [('alive',True),('pid',99),('state','failed'),
                            ('generation',identifier(300)),('servicePid',998)]:
            self.reject(lambda r,f=field,v=value:r['negativeCases'][-1]['terminalEvidence']['stopObservations'][-1]['afterCache'].update({f:v}))

    def test_stop_request_serial_and_deadline_cannot_cross_operations(self):
        self.reject(lambda r:r['negativeCases'][-1]['terminalEvidence']['stopObservations'][-1].update(afterRequestSerial=2))
        self.reject(lambda r:r['negativeCases'][-1]['terminalEvidence']['stopObservations'][-1].update(recoveryRequestSerial=2,afterRequestSerial=2))
        self.reject(lambda r:r['negativeCases'][-1]['terminalEvidence']['stopObservations'][-1].update(endedAtNs=999999999999))

    def test_same_name_cases_require_actual_owned_stop(self):
        for index in (2,3):
            self.reject(lambda r,i=index:r['negativeCases'][i]['terminalEvidence'].update(stopObservations=[]))

    def test_fresh_read_requires_one_real_closed_ipc_observation(self):
        for field,value in [('method','cached-state'),('method',None),('attempts',[])]:
            self.reject(lambda r,f=field,v=value:r['negativeCases'][-1]['terminalEvidence']['freshRead'].update({f:v}))
        for field,value in [('generation',identifier(999)),('alive',True),('pid',11),('state','failed')]:
            self.reject(lambda r,f=field,v=value:r['negativeCases'][-1]['terminalEvidence']['freshRead']['snapshot'].update({f:v}))

    def test_final_cache_must_match_the_fresh_read(self):
        self.reject(lambda r:r['negativeCases'][-1]['terminalEvidence']['finalCache'].update(generation=identifier(999)))

    def test_no_recovery_cut_cannot_claim_an_unowned_live_core(self):
        self.reject(lambda r:r['negativeCases'][0]['terminalEvidence']['postFetchCache']['cache'].update(
            alive=True,pid=9191,state='running',generation=identifier(999)))
        self.reject(lambda r:r['negativeCases'][0]['terminalEvidence']['postFetchCache']['cache'].update(
            generation=identifier(999)))

    def test_active_cut_live_core_must_match_that_requests_owned_stop(self):
        for field,value in [('pid',9191),('servicePid',991),('generation',identifier(999)),
                            ('configuration','0'*64)]:
            self.reject(lambda r,f=field,v=value:r['negativeCases'][-1]['terminalEvidence']['postFetchCache']['cache'].update({f:v}))
        self.reject(lambda r:r['negativeCases'][-1]['terminalEvidence']['stopObservations'][-1].update(
            recoveryRequestSerial=0,afterRequestSerial=0))

    def test_active_cut_cannot_reuse_an_owner_already_closed_before_the_cut(self):
        def mutate(r):
            e=r['negativeCases'][-1]['terminalEvidence']
            e['stopObservations'][-1].update(beganAtNs=e['startedAtNs']+395,endedAtNs=e['startedAtNs']+405)
        self.reject(mutate)

    def test_recovery_can_finish_between_original_observation_and_selection_cut(self):
        value=synthetic_report();e=value['negativeCases'][-1]['terminalEvidence'];base=e['startedAtNs']
        e['recoveries'][0]['completedAtNs']=base+405
        e['stopObservations'][-1].update(beganAtNs=base+401,endedAtNs=base+403)
        e['postFetchCache']['cache']=copy.deepcopy(e['terminalAnchor'])
        e['postFetchCache']['fence']=copy.deepcopy(e['fenceBefore'])
        self.assertIs(e['postFetchCache']['coreAlive'],True)
        self.assertEqual(C.verify_source_route_terminal(value,SOURCE)['cases'],4)

    def test_active_prelaunch_closed_cut_may_have_an_intermediate_generation(self):
        value=synthetic_report();e=value['negativeCases'][-1]['terminalEvidence']
        e['postFetchCache']['coreAlive']=False
        e['postFetchCache']['cache']=dict(e['terminalAnchor'],generation=identifier(998))
        self.assertEqual(C.verify_source_route_terminal(value,SOURCE)['cases'],4)
        for field, bad in (('state','failed'),('pid',99)):
            invalid=copy.deepcopy(value)
            invalid['negativeCases'][-1]['terminalEvidence']['postFetchCache']['cache'][field]=bad
            with self.assertRaises((AssertionError,KeyError,TypeError)):
                C.verify_source_route_terminal(invalid,SOURCE)
        e['postFetchCache']['cache']['configuration']='0'*64
        with self.assertRaises((AssertionError,KeyError,TypeError)):
            C.verify_source_route_terminal(value,SOURCE)

    def test_any_extra_target_contact_or_unknown_count_fails(self):
        for field in synthetic_report()['negativeCases'][0]['before']:
            self.reject(lambda r,f=field:r['negativeCases'][-1]['terminalEvidence']['contactsAfter'].__setitem__(f,
                r['negativeCases'][-1]['terminalEvidence']['contactsAfter'][f]+1))
        self.reject(lambda r:r['negativeCases'][-1]['terminalEvidence']['contactsAfter'].update(ip=True))

    def test_original_source_route_asserts_and_strict_closed_check_remain(self):
        source=ast.parse((ROOT/'tools/gecko/network_sources_contract.py').read_text())
        method=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='verify_source_route')
        assertions=[ast.dump(n,include_attributes=False) for n in ast.walk(method) if isinstance(n,ast.Assert)]
        # Frozen from the actual 64be public verifier; no assertion is replaced by terminal collection.
        digest=hashlib.sha256('\n'.join(assertions).encode()).hexdigest()
        self.assertEqual(digest, '954e2b9bd4a3a89e2ec04e2ab265585143e4a85909c6d22650e256741aa8fe18')
        self.assertTrue(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
                            and n.func.id=='verify_source_route_terminal' for n in ast.walk(method)))

    def test_actual_64be_raw_still_rejected_when_available(self):
        path=ROOT.parents[1]/'work/plan-repairs/ci-64be4b4/connections/bundle/work/gecko-integration/network-source-route-results.json'
        if not path.exists():
            # This portable control preserves the observed old omission and cached true;
            # the private actual raw is separately checked when present, never fabricated as valid.
            value=synthetic_report();value.pop('buildIdentity');value['negativeCases'][-1].pop('terminalEvidence');value['negativeCases'][-1]['coreAliveAfter']=True
        else:
            value=json.loads(path.read_text())
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                             '4406ddcd6c342fe58ab396538681eb0a7fd6130daadb9b376740c04c68ff57a3')
        with self.assertRaises((AssertionError,KeyError,TypeError)):
            C.verify_source_route_terminal(value,value['sourceCommit'])


if __name__ == '__main__':
    unittest.main()
