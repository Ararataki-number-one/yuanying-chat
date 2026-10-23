#!/usr/bin/env python3
"""Synthetic receipts test only the verifier; they are never Android evidence."""
import copy
import importlib.util
import pathlib
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('settings_retry',ROOT/'tests/gecko/run_network_settings_retry.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def receipt():
    names=['Internal completed and late callbacks leave no job records','New external start retains the 32 still-readable completion receipts','Full external receipt capacity rejects new work without deleting results']+[f'synthetic-{i}' for i in range(25)]
    cases=[]
    for fault in ('invalid','timeout'):
        starts=[];ends=[];at=1000
        for i in range(5):
            if i:at=ends[-1]['at']+(2000<<(i-1))
            starts.append({'id':f'{fault}-{i}','at':at,'internal':i>0})
            ends.append({'id':f'{fault}-{i}','at':at+2600,'jobCount':1})
        restored=ends[-1]['at']+100
        cases.append({'fault':fault,'requiredAttempts':5,'faultHits':5,'unavailableObservationHits':5,
                      'pendingStable':True,'activeStable':True,'draftStable':True,'heldBeforeCommit':True,
                      'routeApplied':False,'loadCallsBefore':1,'loadCallsAfter':1,'attempts':starts,'finishes':ends,
                      'availabilityEventChanged':True,'recoveryObservedAt':restored,
                      'priorRetryDeadline':restored+29900,'recoveryAttemptAt':restored+2000})
    return {'status':'passed','sourceCommit':'a'*40,'runNonce':'b'*32,'buildIdentity':{'sourceCommit':'a'*40},
            'actualAndroidExecution':True,'actualGeckoExecution':True,'actualKeystoreEncryption':True,
            'productionDrainInvoked':True,'actualRouteApplication':False,'actualPublicWebsite':False,
            'certificateExceptions':0,'securityEvents':[{'synthetic':True}],
            'testTrust':{'preparedBeforeRuntime':True,'certificateHostnameSanMatches':True},
            'checks':[{'name':name,'pass':True} for name in names],'checkCount':len(names),'retryCases':cases}

class GateTest(unittest.TestCase):
    def verify(self,r):m.verify(r,'a'*40,'b'*32,'c'*64)
    def test_complete_synthetic_receipt(self):self.verify(receipt())
    def test_scope_identity_and_partial_rejected(self):
        for field,value in [('sourceCommit','x'),('runNonce','x'),('actualRouteApplication',True),('productionDrainInvoked',False),('certificateExceptions',1),('checkCount',999)]:
            with self.subTest(field=field):
                r=receipt();r[field]=value
                with self.assertRaises(AssertionError):self.verify(r)
    def test_timer_cannot_impersonate_event(self):
        for field,value in [('availabilityEventChanged',False),('unavailableObservationHits',0),('recoveryAttemptAt',99999999),('priorRetryDeadline',1)]:
            with self.subTest(field=field):
                r=receipt();r['retryCases'][0][field]=value
                with self.assertRaises(AssertionError):self.verify(r)
    def test_repeated_jobs_or_missing_timeout_rejected(self):
        r=receipt();r['retryCases'][0]['finishes'][2]['jobCount']=3
        with self.assertRaises(AssertionError):self.verify(r)
        r=receipt();r['retryCases'][1]['finishes'][0]['at']=r['retryCases'][1]['attempts'][0]['at']+100
        with self.assertRaises(AssertionError):self.verify(r)
    def test_no_backoff_or_wrong_attempt_pair_rejected(self):
        r=receipt();r['retryCases'][0]['attempts'][1]['at']=r['retryCases'][0]['finishes'][0]['at']+20
        with self.assertRaises(AssertionError):self.verify(r)
        r=receipt();r['retryCases'][0]['finishes'][2]['id']='other'
        with self.assertRaises(AssertionError):self.verify(r)

if __name__=='__main__':unittest.main()
