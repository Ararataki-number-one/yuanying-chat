"""Coherent synthetic reservation parser controls; never Android evidence."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
import profile_network_source_terminal_contract_test as F
C=F.C


class ReservationContractTest(unittest.TestCase):
    def reject(self, mutate, joined=False):
        report=F.synthetic_joined_report() if joined else F.synthetic_report()
        mutate(report)
        with self.assertRaises((AssertionError,KeyError,TypeError)):
            C.verify_source_route_terminal(report,F.SOURCE)

    @staticmethod
    def row(report):return report['negativeCases'][-1]
    @classmethod
    def evidence(cls,report):return cls.row(report)['terminalEvidence']
    @classmethod
    def reservation(cls,report):return cls.evidence(report)['reservation']

    def test_coherent_no_join_and_actual_shape_join_controls_pass(self):
        for report in (F.synthetic_report(),F.synthetic_joined_report()):
            self.assertEqual(C.verify_source_route_terminal(report,F.SOURCE)['cases'],4)
            self.assertEqual(report['reservationDiagnostics'],[r['terminalEvidence'] for r in report['negativeCases']])

    def test_reservation_and_top_level_must_both_be_present(self):
        self.reject(lambda r:r.pop('reservationDiagnostics'))
        self.reject(lambda r:r.update(reservationDiagnostics=[]))
        self.reject(lambda r:self.evidence(r).pop('reservation'))
        self.reject(lambda r:[row['terminalEvidence'].pop('reservation') for row in r['negativeCases']])

    def test_top_level_must_match_all_final_per_case_values(self):
        self.reject(lambda r:r['reservationDiagnostics'].reverse())
        def stale(r):
            r['reservationDiagnostics']=copy.deepcopy(r['reservationDiagnostics'])
            self.reservation(r)['callbackCount']=2
        self.reject(stale)
        self.reject(lambda r:r['reservationDiagnostics'].__setitem__(0,copy.deepcopy(r['reservationDiagnostics'][1])))
        def boolean_alias(r):
            r['reservationDiagnostics']=copy.deepcopy(r['reservationDiagnostics'])
            r['reservationDiagnostics'][-1]['reservation']['callbackCount']=True
        self.reject(boolean_alias)

    def test_reservation_case_source_and_nonce_are_bound(self):
        for key,value in [('caseId',F.identifier(999)),('sourceCommit','0'*40),('runNonce','0'*32)]:
            with self.subTest(field=key):self.reject(lambda r,k=key,v=value:self.reservation(r).update({k:v}))
        for group in ('rootObservation',):
            self.reject(lambda r:self.reservation(r)['validation'][group].update(caseId=F.identifier(999)))
        self.reject(lambda r:self.evidence(r)['startObservation'].update(runNonce='0'*32))

    def test_budget_is_original75_and_same_scope_deadline(self):
        for field,value in [('budgetNs',75_000_000_001),('deadlineNs',9999999999999),('beganAtNs',1)]:
            with self.subTest(field=field):self.reject(lambda r,k=field,v=value:self.reservation(r).update({k:v}))
        self.reject(lambda r:self.reservation(r)['admission'].update(atNs=1))

    def test_admission_requires_real_ui_monitor_and_empty_native_state(self):
        for field,value in [('onUiThread',False),('monitorHeld',False),('ownerWasEmpty',False),
                            ('starting',True),('connecting',True),('restartQueued',True),('pendingWaiters',1)]:
            with self.subTest(field=field):self.reject(lambda r,k=field,v=value:self.reservation(r)['admission'].update({k:v}))

    def test_prepare_and_original_body_cannot_escape_original75(self):
        for field in ('admittedAtNs','prepareBeganAtNs','prepareEndedAtNs','originalBeganAtNs','originalEndedAtNs'):
            with self.subTest(field=field):self.reject(lambda r,k=field:self.reservation(r).update({k:self.reservation(r)['deadlineNs']+1}))
        self.reject(lambda r:self.reservation(r)['validation'].update(atNs=self.reservation(r)['deadlineNs']))
        self.reject(lambda r:self.reservation(r).update(prepareEndedAtNs=self.reservation(r)['originalBeganAtNs']+1))

    def test_each_independent_contacts_observation_is_strict(self):
        for group in ('admissionContacts','actualPreparationContacts','actualContactsAfterOriginal'):
            for field in ('fixedTarget','decoyTarget','ip','plainProbe','fixedAllConnected','decoyAllConnected'):
                with self.subTest(group=group,field=field):self.reject(lambda r,g=group,f=field:self.reservation(r)[g].update({f:999}))
        self.reject(lambda r:self.reservation(r)['preparationResult']['contacts'].update(ip=True))
        self.reject(lambda r:self.reservation(r)['admissionContacts'].pop('decoyTarget'))

    def test_rebaseline_cannot_hide_prepare_target_contact(self):
        def rebase(r):
            row=self.row(r);e=self.evidence(r);w=self.reservation(r)
            for value in [row['before'],row['after'],row['request']['before'],row['request']['after'],
                          e['contactsBefore'],e['contactsAfter'],w['actualPreparationContacts'],
                          w['actualContactsAfterOriginal'],w['preparationResult']['contacts']]:value['fixedTarget']=999
        self.reject(rebase)

    def test_managed_stop_source_hashes_and_monitor_are_actual(self):
        self.reject(lambda r:self.reservation(r)['preparationResult'].update(managedCoreStopped=False))
        self.reject(lambda r:self.reservation(r)['preparationResult'].update(entrySnapshotHashValid=False))
        self.reject(lambda r:self.reservation(r).update(prepareMonitorHeld=True))
        self.reject(lambda r:self.reservation(r).update(prepareThreadId=999))
        self.reject(lambda r:self.reservation(r).update(originalThreadId=999))

    def test_exact_one_prep_super_and_callback_and_no_boolean_counts(self):
        for key in ('preparationCount','delegationCount','originalDelegations','callbackCount'):
            for value in (0,2,True):
                with self.subTest(field=key,value=value):self.reject(lambda r,k=key,v=value:self.reservation(r).update({k:v}))
        for key in ('preparations','delegations','callbacks'):
            self.reject(lambda r,k=key:self.reservation(r)['validation'].update({k:2}))

    def test_failure_remains_sticky_and_cannot_qualify(self):
        self.reject(lambda r:self.reservation(r).update(failure='old permanent failure'))
        self.reject(lambda r:self.reservation(r).update(failed=True))
        self.reject(lambda r:self.reservation(r).update(prepared=False))
        self.reject(lambda r:self.reservation(r).update(state='failed'))
        self.reject(lambda r:self.reservation(r)['validation'].update(failed=True))

    def test_owned_worker_has_retired_before_validation(self):
        for key,value in [('scopeOwned',False),('starting',True),('restartQueued',True),('pendingWaiters',1),
                          ('workerCompleted',False),('workerFailed',True)]:
            self.reject(lambda r,k=key,v=value:self.reservation(r)['validation'].update({k:v}))

    def test_root_registration_requires_original_mode2_and_no_queue(self):
        def mutate(r,key,value):
            w=self.reservation(r);e=self.evidence(r)
            for root in (w['realRegistration'],w['validation']['rootObservation']['rootRegistration'],e['startObservation']['rootRegistration']):root[key]=value
        for key,value in [('mode',0),('restartQueuedBefore',True),('restartQueuedAfter',True),('startingBefore',True),
                          ('monitorHeldAfter',False),('waitersBefore',[99]),('exactAppend',False)]:
            with self.subTest(field=key):self.reject(lambda r,k=key,v=value:mutate(r,k,v))
        self.reject(lambda r:self.reservation(r)['realRegistration'].update(request=False))

    def test_actual_worker_identity_and_single_invocation_are_required(self):
        self.reject(lambda r:self.reservation(r).update(invocationId=999))
        self.reject(lambda r:self.reservation(r)['validation']['rootObservation']['workerInvocations'].append(
            copy.deepcopy(self.reservation(r)['validation']['rootObservation']['workerInvocations'][0])))
        self.reject(lambda r:self.evidence(r)['startObservation']['workerInvocations'][0].update(rootCallbackId=999))
        self.reject(lambda r:self.reservation(r)['validation']['rootObservation'].update(errors=['old failure']))

    def test_callback_truth_is_ui_scoped_and_same_terminal_outcome(self):
        for key,value in [('ok',True),('onUiThread',False),('atNs',9999999999999),('threadId',33)]:
            with self.subTest(field=key):self.reject(lambda r,k=key,v=value:self.reservation(r)['actualCallback'].update({k:v}))
        self.reject(lambda r:self.reservation(r)['actualCallback'].update(atNs=self.reservation(r)['originalBeganAtNs']-1))

    def test_same_owned_join_cannot_be_mode0_or_queued_aba(self):
        def mutate(r,key,value):
            w=self.reservation(r);e=self.evidence(r)
            w['validation']['rootObservation']['admissions'][0][key]=value
            e['startObservation']['admissions'][0][key]=value
        for key,value in [('mode',0),('callbackKind','other'),('restartQueuedAfter',True),
                          ('adapterCallbackMatches',False),('rootCallbackRetained',False),('invocationIdAfter',999)]:
            with self.subTest(field=key):self.reject(lambda r,k=key,v=value:mutate(r,k,v),joined=True)

    def test_already_observed_join_cannot_be_omitted_from_both_snapshots(self):
        def erase(r):
            self.reservation(r)['validation']['rootObservation']['admissions']=[]
            self.evidence(r)['startObservation']['admissions']=[]
        self.reject(erase,joined=True)
        self.reject(lambda r:self.reservation(r)['validation'].update(observedAdmissions=0),joined=True)
        self.reject(lambda r:self.evidence(r)['startObservation'].update(admissionCount=True),joined=True)

    def test_final_observer_cannot_rewrite_original_owned_prefix(self):
        self.reject(lambda r:self.evidence(r)['startObservation']['admissions'][0].update(callbackId=999),joined=True)
        self.reject(lambda r:self.evidence(r)['startObservation'].update(workerInvocations=[]))
        self.reject(lambda r:self.evidence(r)['startObservation'].update(rootCallbackId=999))

    def test_policy_blocked_future_recovery_needs_no_invented_start(self):
        report=F.synthetic_report();self.evidence(report)['startObservation'].update(admissions=[],admissionCount=0)
        self.assertEqual(C.verify_source_route_terminal(report,F.SOURCE)['cases'],4)

    def test_recorded_later_recovery_is_bound_and_not_original_owner(self):
        for key,value in [('request',999),('mode',0),('rootCallbackRetained',True),
                          ('startingBefore',True),('invocationIdBefore',999),('restartQueuedAfter',True)]:
            with self.subTest(field=key):self.reject(lambda r,k=key,v=value:self.evidence(r)['startObservation']['admissions'][0].update({k:v}))

    def test_operation_ids_cannot_be_reused_across_negative_cases(self):
        def duplicate(r):
            first=r['negativeCases'][0]['terminalEvidence']['reservation'];e=r['negativeCases'][1]['terminalEvidence'];w=e['reservation']
            callback=first['realRegistration']['callbackId'];registration=first['realRegistration']['registrationId'];invocation=first['invocationId']
            w['invocationId']=invocation
            for root in (w['realRegistration'],w['validation']['rootObservation']['rootRegistration'],e['startObservation']['rootRegistration']):
                root.update(callbackId=callback,registrationId=registration,waitersAfter=[callback])
            for obs in (w['validation']['rootObservation'],e['startObservation']):
                obs['rootCallbackId']=callback;obs['workerInvocations'][0].update(invocationId=invocation,rootRegistrationId=registration,rootCallbackId=callback,waitersBefore=[callback])
        self.reject(duplicate)

    def test_exact_private_review_bad_inputs_stay_rejected_when_available(self):
        path=ROOT.parents[1]/'work/plan-repairs/source-route-reservation-review/reservation-contract-counterexamples.json'
        if path.is_file():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),'24ca2e55a3ef9665d08acef47e6b8ebb641bb8b2af8c1f4c3fc64840605d678a')
            report=json.loads(path.read_text());self.assertEqual(len(report['mutations']),10)
            for item in report['mutations']:
                data=Path(item['file']).read_bytes();self.assertEqual(hashlib.sha256(data).hexdigest(),item['sha256'])
                with self.subTest(originalReview=item['name']),self.assertRaises((AssertionError,KeyError,TypeError)):
                    C.verify_source_route_terminal(json.loads(data),F.SOURCE)


if __name__=='__main__':unittest.main()
