"""Counterfeit lifecycle metadata controls only; no Android/Gecko acceptance.

The device-shaped dictionaries deliberately claim execution as adversarial
validator inputs. They are never written as execution receipts or presented as
evidence that a browser, account, process or device actually ran.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/gecko'))
spec=importlib.util.spec_from_file_location('lifecycle_gate_controls',ROOT/'tools/gecko/check_template_evidence.py')
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
SOURCE='a'*40
TREE='b'*40
JAVA_TEST='tests/browser-runtime/EnvironmentLifecyclePolicyTest.java'

FLAGS={
    'copyAndReset': ['templateCopied','newIdentity','freshAcknowledgements','browserDataNotCopied',
                     'draftNotCopied','sourceIdentityKept','occupiedTargetRejected','failedCopyThenOrdinaryCreation',
                     'resetKeepsLogicalId','resetAdvancesGeneration','pausedIdentityRejected','configurationPreserved',
                     'resetAppliedEvidenceRetired','pendingNetworkRebound','networkSecretUnchanged','preferencesKept',
                     'draftAndTaskCleared','oldConfigurationCallbackRejected','oldHeartbeatRejected',
                     'duplicateResetCannotClearNewLogin','retryCompleted'],
    'resetZero': ['identityKept','configurationKept','sharedRootKept','otherEnvironmentKept','savedDownloadsKept','defaultKept'],
    'deleteOne': ['removed','generationChanged','privateDataGone','otherEnvironmentKept','savedFileKept',
                  'danglingLockRemoved','slotReusable','slotReuseNewIdentity','slotReuseOldCallbackRejected'],
    'deleteZero': ['removed','otherEnvironmentKept','updateSettingsKept','libraryKept','defaultReassigned','lastEnvironmentProtected'],
}


def selected_source(source,path):
    if source!=SOURCE:
        raise ValueError('Counterfeit control source differs')
    candidate=Path(path)
    if candidate.is_absolute() or '..' in candidate.parts:
        raise ValueError('Counterfeit control path differs')
    return (ROOT/candidate).read_bytes()


def host_control():
    with patch.object(gate,'selected_bytes',side_effect=selected_source):
        names=gate.expected_lifecycle_host_names(SOURCE)
    literal_names=re.findall(r'\b(?:check|rejects)\("([^"\n]+)"',(ROOT/JAVA_TEST).read_text())
    assert list(names)==literal_names and len(set(names))==39
    assert len(names)==39
    result=dict(status='passed',actualAndroidExecution=False,passed=39,total=39,
                checks=[{'name':name,'pass':True} for name in names])
    paths=gate.LIFECYCLE_SOURCE_FILES
    return dict(status='passed',sourceCommit=SOURCE,sourceTree=TREE,sourceDirty=False,
                sourceUnchangedDuringChecks=True,actualAndroidExecution=False,
                files={path:hashlib.sha256(selected_source(SOURCE,path)).hexdigest() for path in paths},
                results=[{'test':'EnvironmentLifecyclePolicyTest','exitCode':0,'output':json.dumps(result)}])


def identity():
    return dict(schema=1,package='local.pocketchat.test',sourceCommit=SOURCE,sourceTree=TREE,dirtySource=False,
                version='1.7.0',versionCode=52,sdkCoordinate='org.mozilla.geckoview:geckoview:157.0.20261005135250',
                apkSha256='c'*64,apkBytes=100,buildStampSha256='d'*64)


def cookie_event(context,action,populated):
    expected='synthetic-environment-'+str(context) if populated else None
    result=dict(context=str(context),action=action,localStorage=expected,indexedDB=expected,cache=expected,
                workerToken=expected,cookie='probe='+expected if populated else '',serviceWorkers=int(populated),
                nativeCookies='probe='+expected+'; nativeOnly='+expected if populated else '')
    return dict(kind='fixture',result=result,nativeContext='environment-'+str(context),processSlot=context-1)


def device_control():
    # This is metadata, not an Android run. The positive case exercises a parser
    # branch; negative mutations prove that unbacked summaries cannot satisfy it.
    with patch.object(gate,'selected_bytes',side_effect=selected_source):
        required={action:gate.lifecycle_flag_names(SOURCE,action) for action in ('copyAndReset','resetZero','deleteOne')}
    # Independently keep the original required flags. Deriving names must never
    # derive success values or silently erase a currently promised assertion.
    for action,names in required.items():assert set(FLAGS[action]).issubset(names),(action,names)
    required['deleteZero']=FLAGS['deleteZero']
    management={action:dict(action=action,**{name:True for name in flags}) for action,flags in required.items()}
    def managed(action):return dict(kind='environmentManagement',result=copy.deepcopy(management[action]))
    steps=[cookie_event(1,'seed',True),cookie_event(2,'seed',True),managed('copyAndReset'),
           cookie_event(2,'read',False),cookie_event(1,'read',True),cookie_event(2,'seed',True),
           managed('resetZero'),cookie_event(1,'read',False),cookie_event(2,'read',True),
           managed('deleteOne'),cookie_event(2,'read',False),managed('deleteZero')]
    return dict(status='passed',actualAndroidExecution=True,diagnosticOnly=False,releaseMode=True,
                sourceCommit=SOURCE,environmentManagement=management,steps=steps,
                eventTransport={'schema':1,'buildIdentity':identity(),'invocations':[]})


def change_output(host,edit):
    result=json.loads(host['results'][0]['output']);edit(result)
    host['results'][0]['output']=json.dumps(result)


class LifecycleGateCounterfeitControls(unittest.TestCase):
    def host(self,value):
        with patch.object(gate,'selected_bytes',side_effect=selected_source):
            return gate.verify_lifecycle_host(value,SOURCE)

    def device(self,value,selected_identity=None):
        with patch.object(gate,'selected_bytes',side_effect=selected_source):
            return gate.verify_lifecycle_device(value,SOURCE,identity=selected_identity)

    def test_complete_host_controls_are_exactly_thirty_nine_without_android_claim(self):
        value=host_control();self.assertEqual(self.host(value),39)
        self.assertIs(value['actualAndroidExecution'],False)

    def test_missing_duplicate_or_failed_host_group_is_rejected(self):
        for mutate in [lambda v:v.update(results=[]),lambda v:v['results'].append(copy.deepcopy(v['results'][0])),
                       lambda v:v['results'][0].update(exitCode=1)]:
            value=host_control();mutate(value)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):self.host(value)

    def test_equal_counts_cannot_hide_wrong_missing_reordered_or_duplicate_names(self):
        changes=[lambda r:r['checks'][0].update(name='counterfeit unrelated assertion'),
                 lambda r:r['checks'].reverse(),lambda r:r['checks'].__setitem__(1,copy.deepcopy(r['checks'][0])),
                 lambda r:r['checks'].pop(),lambda r:r.update(passed=40,total=40)]
        for mutate in changes:
            value=host_control();change_output(value,mutate)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):self.host(value)

    def test_host_false_numeric_flags_and_runtime_promotion_fail(self):
        for mutate in [lambda r:r['checks'][0].update(**{'pass':False}),lambda r:r['checks'][0].update(**{'pass':1}),
                       lambda r:r.update(actualAndroidExecution=True),lambda r:r.update(passed=True,total=True),
                       lambda r:r.update(status='failed')]:
            value=host_control();change_output(value,mutate)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):self.host(value)

    def test_selected_lifecycle_sources_cannot_omit_relabel_or_corrupt_hashes(self):
        def verify_files(value,source=SOURCE):
            with patch.object(gate,'selected_bytes',side_effect=selected_source):
                return gate.verify_lifecycle_sources(value,source)
        files=host_control()['files'];verify_files(files)
        self.assertIn(JAVA_TEST,gate.LIFECYCLE_SOURCE_FILES)
        for path in gate.LIFECYCLE_SOURCE_FILES:
            for change in ('missing','hash','relative','absolute'):
                value=dict(files)
                if change=='missing':value.pop(path)
                elif change=='hash':value[path]='f'*64
                elif change=='relative':value['../'+path]=value.pop(path)
                else:value['/'+path]=value.pop(path)
                with self.subTest(path=path,change=change),self.assertRaises(ValueError):verify_files(value)
        with self.assertRaises(ValueError):verify_files(files,'f'*40)

    def test_complete_counterfeit_device_parser_branch_retains_scope_boundary(self):
        value=device_control();self.device(value);self.device(value,identity())
        # The test has checked dictionaries only, never emitted Android evidence.
        self.assertEqual(value['eventTransport']['invocations'],[])

    def test_device_scope_source_and_presence_are_mandatory(self):
        changes=[lambda v:v.update(status='failed'),lambda v:v.update(actualAndroidExecution=False),
                 lambda v:v.update(actualAndroidExecution=1),lambda v:v.update(diagnosticOnly=True),
                 lambda v:v.update(releaseMode=False),lambda v:v.update(sourceCommit='f'*40),
                 lambda v:v.pop('environmentManagement'),lambda v:v.update(steps=[])]
        for mutate in changes:
            value=device_control();mutate(value)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):self.device(value)

    def test_every_literal_required_lifecycle_flag_is_required_and_boolean_true(self):
        for action in ('copyAndReset','resetZero','deleteOne'):
            with patch.object(gate,'selected_bytes',side_effect=selected_source):
                flags=gate.lifecycle_flag_names(SOURCE,action)
            for flag in flags:
                for replacement in ('missing',False,1):
                    value=device_control()
                    if replacement=='missing':value['environmentManagement'][action].pop(flag)
                    else:value['environmentManagement'][action][flag]=replacement
                    # Keep the step equal so the negative tests the actual flag,
                    # rather than only report/step consistency.
                    for step in value['steps']:
                        if step['kind']=='environmentManagement' and step['result']['action']==action:
                            step['result']=copy.deepcopy(value['environmentManagement'][action])
                    with self.subTest(action=action,flag=flag,value=replacement),self.assertRaises(ValueError):self.device(value)

    def test_missing_duplicate_relabelled_or_unequal_management_steps_fail(self):
        changes=[lambda v:v['steps'].__delitem__(2),lambda v:v['steps'].append(copy.deepcopy(v['steps'][2])),
                 lambda v:v['steps'][2]['result'].update(action='unrelated'),
                 lambda v:v['steps'][2]['result'].update(templateCopied=False)]
        for mutate in changes:
            value=device_control();mutate(value)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):self.device(value)

    def test_summary_flags_without_actual_cookie_steps_cannot_pass(self):
        value=device_control();value['steps']=[step for step in value['steps'] if step['kind']!='fixture']
        with self.assertRaises(ValueError):self.device(value)

    def test_cookie_reset_requires_order_environment_native_and_dom_observations(self):
        changes=[lambda v:v['steps'].__delitem__(3),lambda v:v['steps'].__setitem__(3,cookie_event(1,'read',False)),
                 lambda v:v['steps'][3]['result'].update(nativeCookies='probe=old-login'),
                 lambda v:v['steps'][3]['result'].update(cookie='probe=old-login'),
                 lambda v:v['steps'][3]['result'].update(localStorage='old-login'),
                 lambda v:v['steps'][3]['result'].update(serviceWorkers=1),
                 lambda v:v['steps'][3]['result'].pop('workerToken'),
                 lambda v:v['steps'].__setitem__(4,cookie_event(1,'read',False)),
                 lambda v:v['steps'].__setitem__(7,cookie_event(1,'read',True)),
                 lambda v:v['steps'].__setitem__(8,cookie_event(2,'read',False)),
                 lambda v:v['steps'][3].update(processSlot=0),
                 lambda v:v['steps'][3].update(nativeContext='environment-1')]
        for mutate in changes:
            value=device_control();mutate(value)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):self.device(value)

    def test_supplied_template_apk_identity_cannot_certify_missing_event_transport(self):
        value=device_control();value.pop('eventTransport')
        with self.assertRaises(ValueError):self.device(value,identity())
        value=device_control();value['eventTransport']['buildIdentity']['apkSha256']='f'*64
        with self.assertRaises(ValueError):self.device(value,identity())

    def test_empty_errors_and_unknown_non_boolean_success_flags_are_not_accepted(self):
        changes=[lambda v:v.update(error=''),lambda v:v['steps'][3]['result'].update(error='')]
        for field,value in [('error',''),('counterfeitAdditionalFlag',False),('counterfeitAdditionalFlag',1)]:
            def management_change(report,field=field,value=value):
                report['environmentManagement']['copyAndReset'][field]=value
                report['steps'][2]['result']=copy.deepcopy(report['environmentManagement']['copyAndReset'])
            changes.append(management_change)
        for mutate in changes:
            value=device_control();mutate(value)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):self.device(value)


if __name__=='__main__':unittest.main()
