#!/usr/bin/env python3
"""Synthetic receipts test only the verifier; they are never Android evidence."""
import copy
import importlib.util
import pathlib
import os
import shutil
import subprocess
import tempfile
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
            starts.append({'id':('internal:' if i else '')+f'{fault}-{i}','at':at,'internal':i>0})
            ends.append({'id':starts[-1]['id'],'at':at+2600,'jobCount':1})
        restored=ends[-1]['at']+100
        cases.append({'case':'retry-'+fault,'recoveryId':'internal:'+fault+'-recovery','fault':fault,'requiredAttempts':5,'faultHits':5,'unavailableObservationHits':5,
                      'pendingStable':True,'activeStable':True,'draftStable':True,'heldBeforeCommit':True,
                      'routeApplied':False,'loadCallsBefore':1,'loadCallsAfter':1,'attempts':starts,'finishes':ends,
                      'availabilityEventChanged':True,'recoveryObservedAt':restored,
                      'priorRetryDeadline':restored+29900,'recoveryAttemptAt':restored+2000})
    ledger={'schema':1,'cases':[],'callbacks':[]}
    for i,case in enumerate(cases):
        attempts=[dict(id=a['id'],started=a['at'],retired=b['at'],jobCount=b['jobCount']) for a,b in zip(case['attempts'],case['finishes'])]
        attempts.append(dict(id=case['recoveryId'],started=case['recoveryAttemptAt'],retired=case['recoveryAttemptAt']+100,jobCount=2))
        ledger['cases'].append(dict(case=case['case'],externalId=attempts[0]['id'],environmentId='11111111-2222-4333-8444-555555555555',generation=1,snapshotHash=str(i)*64,closed=True,attempts=attempts))
        ledger['callbacks'].extend(dict(id=a['id'],case=case['case'],at=a['retired'],wasActive=True,isRetired=True,jobCount=a['jobCount']) for a in attempts)
    return {'retryLedger':ledger,'status':'passed','sourceCommit':'a'*40,'runNonce':'b'*32,'buildIdentity':{'sourceCommit':'a'*40},
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
    def test_late_callback_remains_bound_to_old_case(self):
        r=receipt();old=r['retryLedger']['callbacks'][5]
        r['retryLedger']['callbacks'].insert(6,dict(old,at=old['at']+1,wasActive=False))
        self.verify(r)
        r['retryLedger']['callbacks'][6]['case']='retry-timeout'
        with self.assertRaises(AssertionError):self.verify(r)
    def test_missing_owned_retirement_or_unowned_callback_rejected(self):
        r=receipt();r['retryLedger']['callbacks'].pop()
        with self.assertRaises(AssertionError):self.verify(r)
        r=receipt();r['retryLedger']['callbacks'].append(dict(r['retryLedger']['callbacks'][0],id='unowned',wasActive=False))
        with self.assertRaises(AssertionError):self.verify(r)
        r=receipt();r['retryLedger']['cases'][0]['closed']=False
        with self.assertRaises(AssertionError):self.verify(r)
    def test_wrong_candidate_or_recovery_identity_rejected(self):
        r=receipt();r['retryLedger']['cases'][1]['snapshotHash']=r['retryLedger']['cases'][0]['snapshotHash']
        with self.assertRaises(AssertionError):self.verify(r)
        r=receipt();r['retryCases'][1]['recoveryId']=r['retryCases'][0]['recoveryId']
        with self.assertRaises(AssertionError):self.verify(r)
    def test_ledger_identity_requires_canonical_uuid_exact_generation_and_hex_digest(self):
        for field, value in [('environmentId','not-an-environment'),('environmentId','11111111222243338444555555555555'),
                             ('environmentId','AAAAAAAA-BBBB-4CCC-8DDD-EEEEEEEEEEEE'),('environmentId',True),
                             ('generation',True),('generation',1.0),('generation',-1),('snapshotHash','x'*64),('snapshotHash',64)]:
            with self.subTest(field=field,value=value):
                r=receipt();r['retryLedger']['cases'][0][field]=value
                with self.assertRaises(AssertionError):self.verify(r)
        for field,value in [('environmentId','aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'),('generation',2)]:
            with self.subTest(secondCase=field):
                r=receipt();r['retryLedger']['cases'][1][field]=value
                with self.assertRaises(AssertionError):self.verify(r)
    def test_real_java_ledger_replays_delayed_callback_and_rejects_lost_jobs(self):
        java=os.environ.get('PROFILE_JAVA') or shutil.which('java')
        self.assertTrue(java,'Java 17 is required for actual fixture ledger controls')
        with tempfile.TemporaryDirectory() as tmp:
            sources=[ROOT/'tests/gecko/RetryAttemptLedger.java',ROOT/'tests/browser-runtime/RetryAttemptLedgerTest.java']
            compiled=subprocess.run([java,'-m','jdk.compiler/com.sun.tools.javac.Main','-encoding','UTF-8','-d',tmp,*map(str,sources)],text=True,capture_output=True)
            self.assertEqual(compiled.returncode,0,compiled.stdout+compiled.stderr)
            ran=subprocess.run([java,'-cp',tmp,'local.pocketchat.RetryAttemptLedgerTest'],text=True,capture_output=True)
            self.assertEqual(ran.returncode,0,ran.stdout+ran.stderr)
            self.assertIn('actualAndroidExecution=false',ran.stdout)
    def test_no_backoff_or_wrong_attempt_pair_rejected(self):
        r=receipt();r['retryCases'][0]['attempts'][1]['at']=r['retryCases'][0]['finishes'][0]['at']+20
        with self.assertRaises(AssertionError):self.verify(r)
        r=receipt();r['retryCases'][0]['finishes'][2]['id']='other'
        with self.assertRaises(AssertionError):self.verify(r)

if __name__=='__main__':unittest.main()
