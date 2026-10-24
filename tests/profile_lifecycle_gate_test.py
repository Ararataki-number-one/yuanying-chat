"""Counterfeit lifecycle metadata controls only; no Android/Gecko acceptance.

The device-shaped dictionaries deliberately claim execution as adversarial
validator inputs. They are never written as execution receipts or presented as
evidence that a browser, account, process or device actually ran.
"""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch
from profile_sdk_metadata import DERIVED_MANIFEST

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/gecko'))
spec=importlib.util.spec_from_file_location('lifecycle_gate_controls',ROOT/'tools/gecko/check_template_evidence.py')
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
SOURCE='a'*40
TREE='b'*40
JAVA_TEST='tests/browser-runtime/EnvironmentLifecyclePolicyTest.java'
CLEANUP_ACTION='readingFixtureCookieCleanup'
CLEANUP_JAVA='tests/gecko/GeckoIntegrationTestActivity.java'
CLEANUP_RUNNER='tests/gecko/run_device.py'
GATE_SOURCE='tools/gecko/check_template_evidence.py'
CLEANUP_DEPENDENCIES=('tools/gecko/integration_event_contract.py','tools/gecko/profile_invocation_contract.py')

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
    if path==DERIVED_MANIFEST:
        raise FileNotFoundError('Historical counterfeit lifecycle source has no derived SDK manifest')
    return (ROOT/candidate).read_bytes()


def legacy_selected_source(source,path):
    raw=selected_source(source,path)
    if path==CLEANUP_RUNNER:
        raw=raw.replace(b"run(2,'readingFixtureCookieCleanup','readingFixtureCookieCleanup')",b'legacy_cleanup_control()')
    elif path==CLEANUP_JAVA:
        raw=raw.replace(b'"readingFixtureCookieCleanup".equals(action)',b'"legacyCleanupControl".equals(action)')
    return raw


def host_control(source_reader=selected_source):
    with patch.object(gate,'selected_bytes',side_effect=source_reader):
        names=gate.expected_lifecycle_host_names(SOURCE)
        paths=gate.lifecycle_required_source_files(SOURCE)
    literal_names=re.findall(r'\b(?:check|rejects)\("([^"\n]+)"',(ROOT/JAVA_TEST).read_text())
    assert list(names)==literal_names and len(set(names))==39
    assert len(names)==39
    result=dict(status='passed',actualAndroidExecution=False,passed=39,total=39,
                checks=[{'name':name,'pass':True} for name in names])
    return dict(status='passed',sourceCommit=SOURCE,sourceTree=TREE,sourceDirty=False,
                sourceUnchangedDuringChecks=True,actualAndroidExecution=False,
                files={path:hashlib.sha256(source_reader(SOURCE,path)).hexdigest() for path in paths},
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


def cleanup_event():
    return dict(kind=CLEANUP_ACTION,nativeContext='environment-2',processSlot=1,result=dict(
        schema=1,cookie='readingBounds=controlled-fixture',cookiePath='/',processSlot=1,
        runNonce='e'*32,invocation=41,origin='http://127.0.0.1:8765',
        url='http://127.0.0.1:8765/reading-cookie-retirement?runNonce='+'e'*32,
        sameSession=True,sameDocument=True,sameUrl=True,sessionBefore=17,sessionAfter=17,
        documentBefore=1720000000123.25,documentAfter=1720000000123.25,
        beforeDomCookies='probe=synthetic-environment-2; readingBounds=controlled-fixture; unknown=dom=value',
        afterDomCookies='unknown=dom=value; probe=synthetic-environment-2',
        nativeBefore='readingBounds=controlled-fixture; nativeOnly=synthetic-environment-2; unknown=native=value',
        nativeAfter='unknown=native=value; nativeOnly=synthetic-environment-2',
        readingFixtureCookieRemovedFromDom=True,readingFixtureCookieRemovedFromNative=True,
        otherDomCookiesPreserved=True,otherNativeCookiesPreserved=True))


def cleanup_transfer(step,build_identity):
    result=step['result'];nonce=result.get('runNonce','e'*32);command=result.get('invocation',41)
    envelope=dict(schema=1,sourceCommit=build_identity['sourceCommit'],buildIdentity=copy.deepcopy(build_identity),
                  runNonce=nonce,fixtureAction=CLEANUP_ACTION,command=command,sequence=1,
                  nativeContext='environment-2',processSlot=1,observedAtElapsedRealtime=1000,
                  event=copy.deepcopy(step))
    raw=json.dumps(envelope,separators=(',',':'))+'\n'
    receipt=dict(kind='eventReceipt',schema=1,runNonce=nonce,fixtureAction=CLEANUP_ACTION,
                 command=command,sequence=1,nativeContext='environment-2',processSlot=1,
                 eventKind=CLEANUP_ACTION,payloadBytes=len(raw.encode()),
                 payloadSha256=hashlib.sha256(raw.encode()).hexdigest())
    return dict(runNonce=nonce,fixtureAction=CLEANUP_ACTION,processSlot=1,
                events=[dict(receipt=receipt,rawUtf8=raw)])


def change_cleanup(report,edit):
    # Keep the summary, step and owned raw event equal so semantic mutations
    # exercise the cleanup contract instead of only equality between receipts.
    step=next(step for step in report['steps'] if step['kind']==CLEANUP_ACTION)
    edit(step['result']);report[CLEANUP_ACTION]=copy.deepcopy(step['result'])
    report['eventTransport']['invocations']=[cleanup_transfer(step,report['eventTransport']['buildIdentity'])]


def device_control(cleanup=True):
    # This is metadata, not an Android run. The positive case exercises a parser
    # branch; negative mutations prove that unbacked summaries cannot satisfy it.
    with patch.object(gate,'selected_bytes',side_effect=selected_source):
        required={action:gate.lifecycle_flag_names(SOURCE,action) for action in ('copyAndReset','resetZero','deleteOne','deleteZero')}
    # Independently keep the original required flags. Deriving names must never
    # derive success values or silently erase a currently promised assertion.
    for action,names in required.items():assert set(FLAGS[action]).issubset(names),(action,names)
    management={action:dict(action=action,**{name:True for name in flags}) for action,flags in required.items()}
    def managed(action):return dict(kind='environmentManagement',result=copy.deepcopy(management[action]))
    steps=[cookie_event(1,'seed',True),cookie_event(2,'seed',True),managed('copyAndReset'),
           cookie_event(2,'read',False),cookie_event(1,'read',True),cookie_event(2,'seed',True),
           managed('resetZero'),cookie_event(1,'read',False),cookie_event(2,'read',True),
           managed('deleteOne'),cookie_event(2,'read',False),managed('deleteZero')]
    report=dict(status='passed',actualAndroidExecution=True,diagnosticOnly=False,releaseMode=True,
                sourceCommit=SOURCE,environmentManagement=management,steps=steps,
                eventTransport={'schema':1,'buildIdentity':identity(),'invocations':[]})
    if cleanup:
        step=cleanup_event();report['steps'].insert(0,step)
        report[CLEANUP_ACTION]=copy.deepcopy(step['result'])
        report['eventTransport']['invocations']=[cleanup_transfer(step,identity())]
    return report


def change_output(host,edit):
    result=json.loads(host['results'][0]['output']);edit(result)
    host['results'][0]['output']=json.dumps(result)


def release_stage_python_files():
    # Read only declared Python copy paths. Never execute publisher setup,
    # evidence validation, APK handling, remote reads or publication commands.
    tree=ast.parse((ROOT/'tools/publish-gecko-release.py').read_text())
    files=set();stage=Path('/synthetic-release-stage')
    def path_value(node,bindings):
        if isinstance(node,ast.Name):return bindings.get(node.id)
        if isinstance(node,ast.Constant) and isinstance(node.value,str):return node.value
        if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Div):
            left=path_value(node.left,bindings);right=path_value(node.right,bindings)
            if left is not None and right is not None:return Path(left)/right
        return None
    def visit(statements,bindings):
        for statement in statements:
            if isinstance(statement,ast.If):
                visit(statement.body,bindings);visit(statement.orelse,bindings)
            elif isinstance(statement,ast.For) and isinstance(statement.target,ast.Name):
                try:values=ast.literal_eval(statement.iter)
                except (ValueError,TypeError):continue
                if not isinstance(values,(list,tuple)) or not all(isinstance(value,str) for value in values):continue
                for value in values:visit(statement.body,dict(bindings,**{statement.target.id:value}))
            elif isinstance(statement,ast.Expr) and isinstance(statement.value,ast.Call):
                call=statement.value
                if not isinstance(call.func,ast.Attribute) or not isinstance(call.func.value,ast.Name) or call.func.value.id!='shutil' or call.func.attr!='copy2' or len(call.args)!=2:continue
                source=path_value(call.args[0],bindings);target=path_value(call.args[1],bindings)
                if not isinstance(source,Path) or not isinstance(target,Path):continue
                if source.is_relative_to(ROOT/'tools/gecko') and target.is_relative_to(stage/'tools/gecko') and source.suffix=='.py':
                    relative=source.relative_to(ROOT)
                    if target.relative_to(stage)!=relative:raise AssertionError('Publisher Python source and stage paths differ')
                    files.add(str(relative))
    visit(tree.body,dict(root=ROOT,stage=stage))
    return files


class LifecycleGateCounterfeitControls(unittest.TestCase):
    def host(self,value,source_reader=selected_source):
        with patch.object(gate,'selected_bytes',side_effect=source_reader):
            return gate.verify_lifecycle_host(value,SOURCE)

    def device(self,value,selected_identity=None,source_reader=selected_source):
        with patch.object(gate,'selected_bytes',side_effect=source_reader):
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
        with patch.object(gate,'selected_bytes',side_effect=selected_source):
            paths=gate.lifecycle_required_source_files(SOURCE)
        for path in paths:
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
        self.assertEqual(len(value['eventTransport']['invocations']),1)
        self.assertEqual(value['steps'][0]['kind'],CLEANUP_ACTION)

    def test_device_scope_source_and_presence_are_mandatory(self):
        changes=[lambda v:v.update(status='failed'),lambda v:v.update(actualAndroidExecution=False),
                 lambda v:v.update(actualAndroidExecution=1),lambda v:v.update(diagnosticOnly=True),
                 lambda v:v.update(releaseMode=False),lambda v:v.update(sourceCommit='f'*40),
                 lambda v:v.pop('environmentManagement'),lambda v:v.update(steps=[])]
        for mutate in changes:
            value=device_control();mutate(value)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):self.device(value)

    def test_new_default_deletion_action_cannot_be_omitted(self):
        value=device_control();value['environmentManagement'].pop('deleteZero')
        with self.assertRaises(ValueError):self.device(value)
        value=device_control();value['steps']=[step for step in value['steps'] if not(step['kind']=='environmentManagement' and step['result']['action']=='deleteZero')]
        with self.assertRaises(ValueError):self.device(value)

    def test_every_literal_required_lifecycle_flag_is_required_and_boolean_true(self):
        for action in ('copyAndReset','resetZero','deleteOne','deleteZero'):
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
        changes=[lambda v:v['steps'].__delitem__(3),lambda v:v['steps'].append(copy.deepcopy(v['steps'][3])),
                 lambda v:v['steps'][3]['result'].update(action='unrelated'),
                 lambda v:v['steps'][3]['result'].update(templateCopied=False)]
        for mutate in changes:
            value=device_control();mutate(value)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):self.device(value)

    def test_summary_flags_without_actual_cookie_steps_cannot_pass(self):
        value=device_control();value['steps']=[step for step in value['steps'] if step['kind']!='fixture']
        with self.assertRaises(ValueError):self.device(value)

    def test_cookie_reset_requires_order_environment_native_and_dom_observations(self):
        changes=[lambda v:v['steps'].__delitem__(4),lambda v:v['steps'].__setitem__(4,cookie_event(1,'read',False)),
                 lambda v:v['steps'][4]['result'].update(nativeCookies='probe=old-login'),
                 lambda v:v['steps'][4]['result'].update(cookie='probe=old-login'),
                 lambda v:v['steps'][4]['result'].update(localStorage='old-login'),
                 lambda v:v['steps'][4]['result'].update(serviceWorkers=1),
                 lambda v:v['steps'][4]['result'].pop('workerToken'),
                 lambda v:v['steps'].__setitem__(5,cookie_event(1,'read',False)),
                 lambda v:v['steps'].__setitem__(8,cookie_event(1,'read',True)),
                 lambda v:v['steps'].__setitem__(9,cookie_event(2,'read',False)),
                 lambda v:v['steps'][4].update(processSlot=0),
                 lambda v:v['steps'][4].update(nativeContext='environment-1')]
        for mutate in changes:
            value=device_control();mutate(value)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):self.device(value)

    def test_supplied_template_apk_identity_cannot_certify_missing_event_transport(self):
        value=device_control();value.pop('eventTransport')
        with self.assertRaises(ValueError):self.device(value,identity())
        value=device_control();value['eventTransport']['buildIdentity']['apkSha256']='f'*64
        with self.assertRaises(ValueError):self.device(value,identity())

    def test_empty_errors_and_unknown_non_boolean_success_flags_are_not_accepted(self):
        changes=[lambda v:v.update(error=''),lambda v:v['steps'][4]['result'].update(error='')]
        for field,value in [('error',''),('counterfeitAdditionalFlag',False),('counterfeitAdditionalFlag',1)]:
            def management_change(report,field=field,value=value):
                report['environmentManagement']['copyAndReset'][field]=value
                report['steps'][3]['result']=copy.deepcopy(report['environmentManagement']['copyAndReset'])
            changes.append(management_change)
        for mutate in changes:
            value=device_control();mutate(value)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):self.device(value)

    def test_cleanup_capability_comes_from_both_selected_source_declarations(self):
        with patch.object(gate,'selected_bytes',side_effect=selected_source):
            self.assertIs(gate.requires_reading_fixture_cleanup(SOURCE),True)
            paths=gate.lifecycle_required_source_files(SOURCE)
        self.assertIn(CLEANUP_JAVA,paths);self.assertIn(GATE_SOURCE,paths)
        for path in CLEANUP_DEPENDENCIES:self.assertIn(path,paths)
        with patch.object(gate,'selected_bytes',side_effect=legacy_selected_source):
            self.assertIs(gate.requires_reading_fixture_cleanup(SOURCE),False)
            self.assertEqual(gate.lifecycle_required_source_files(SOURCE),gate.LIFECYCLE_SOURCE_FILES)
        for omitted in (CLEANUP_JAVA,CLEANUP_RUNNER):
            def one_sided(source,path,omitted=omitted):
                return legacy_selected_source(source,path) if path==omitted else selected_source(source,path)
            with self.subTest(omitted=omitted),patch.object(gate,'selected_bytes',side_effect=one_sided):
                with self.assertRaises(ValueError):gate.requires_reading_fixture_cleanup(SOURCE)
                with self.assertRaises(ValueError):gate.lifecycle_required_source_files(SOURCE)
                with self.assertRaises(ValueError):gate.verify_lifecycle_device(device_control(),SOURCE)

    def test_legacy_selected_source_keeps_original_twelve_step_receipt_and_hashes_valid(self):
        value=device_control(cleanup=False)
        self.assertEqual(len(value['steps']),12)
        self.assertEqual(value['eventTransport']['invocations'],[])
        self.device(value,identity(),source_reader=legacy_selected_source)
        host=host_control(legacy_selected_source)
        self.assertEqual(self.host(host,legacy_selected_source),39)
        self.assertNotIn(CLEANUP_JAVA,host['files']);self.assertNotIn(GATE_SOURCE,host['files'])
        for path in CLEANUP_DEPENDENCIES:self.assertNotIn(path,host['files'])
        with patch.object(gate,'selected_bytes',side_effect=legacy_selected_source):
            gate.verify_lifecycle_sources(host['files'],SOURCE)
        # Merely relabelling the old report to the capable selected source does
        # not supply either the new raw observation or the new producer hashes.
        with self.assertRaises(ValueError):self.device(value,identity())
        with patch.object(gate,'selected_bytes',side_effect=selected_source):
            with self.assertRaises(ValueError):gate.verify_lifecycle_sources(host['files'],SOURCE)

    def test_cleanup_step_and_summary_must_be_unique_identical_and_before_both_seeds(self):
        def moved(report):report['steps'].insert(2,report['steps'].pop(0))
        def displaced(report):report['steps'].insert(1,dict(kind='unrelated',result={}))
        changes=[lambda v:v.pop(CLEANUP_ACTION),lambda v:v['steps'].pop(0),
                 lambda v:v['steps'].append(copy.deepcopy(v['steps'][0])),moved,displaced,
                 lambda v:v[CLEANUP_ACTION].update(sessionAfter=99),
                 lambda v:v['steps'][0]['result'].update(documentAfter=99),
                 lambda v:v['steps'][0].update(kind='nativeCheckpoint')]
        for mutate in changes:
            value=device_control();mutate(value)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):self.device(value)

    def test_cleanup_environment_and_result_types_are_required(self):
        changes=[lambda v:v['steps'][0].update(nativeContext='environment-1'),
                 lambda v:v['steps'][0].update(processSlot=0),
                 lambda v:v['steps'][0].update(processSlot=True)]
        for mutate in changes:
            value=device_control();mutate(value)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):self.device(value)
        replacements={'schema':(None,True,2),'cookie':('readingBounds=unknown','probe=controlled-fixture'),
                      'cookiePath':('/browser-reading',''),'processSlot':(0,True),
                      'runNonce':('', 'E'*32, 'e'*31),'invocation':(0,-1,True,'41'),
                      'origin':('https://127.0.0.1:8765','http://localhost:8765'),
                      'url':('http://127.0.0.1:8765/browser-reading?command=40',
                             'http://127.0.0.1:8765/reading-cookie-retirement?runNonce='+'f'*32,
                             'http://127.0.0.1:8765/reading-cookie-retirement?runNonce='+'e'*32+'&extra=1')}
        for field,rejected in replacements.items():
            for replacement in ('missing',*rejected):
                value=device_control()
                edit=(lambda r:r.pop(field)) if replacement=='missing' else (lambda r:r.update({field:replacement}))
                # Invalid nonce/command inputs still need a raw envelope for the
                # negative case; they are intentionally adversarial metadata.
                change_cleanup(value,edit)
                with self.subTest(field=field,value=replacement),self.assertRaises(ValueError):self.device(value)

    def test_cleanup_same_page_receipts_and_success_flags_cannot_be_fabricated(self):
        replacements={'sameSession':(False,1),'sameDocument':(False,1),'sameUrl':(False,1),
                      'sessionBefore':(0,True,'17'),'sessionAfter':(0,18,True),
                      'documentBefore':(0,True,'1720000000123.25',float('inf'),float('nan')),
                      'documentAfter':(0,1720000000124.25,True,float('inf'),float('nan')),
                      'readingFixtureCookieRemovedFromDom':(False,1),
                      'readingFixtureCookieRemovedFromNative':(False,1),
                      'otherDomCookiesPreserved':(False,1),'otherNativeCookiesPreserved':(False,1)}
        for field,rejected in replacements.items():
            for replacement in ('missing',*rejected):
                value=device_control()
                change_cleanup(value,(lambda r:r.pop(field)) if replacement=='missing' else
                                     (lambda r:r.update({field:replacement})))
                with self.subTest(field=field,value=replacement),self.assertRaises(ValueError):self.device(value)
        value=device_control();change_cleanup(value,lambda r:r.update(error=''))
        with self.assertRaises(ValueError):self.device(value)

    def test_cleanup_rejects_unknown_duplicate_missing_or_remaining_marker_values(self):
        for before,after in (('beforeDomCookies','afterDomCookies'),('nativeBefore','nativeAfter')):
            changes=[lambda r:r.update({before:r[before].replace('readingBounds=controlled-fixture','readingBounds=unknown')}),
                     lambda r:r.update({before:r[before]+'; readingBounds=controlled-fixture'}),
                     lambda r:r.update({before:r[before]+'; readingBounds=unknown'}),
                     lambda r:r.update({before:r[before].replace('readingBounds=controlled-fixture; ', '')}),
                     lambda r:r.update({after:r[after]+'; readingBounds=controlled-fixture'}),
                     lambda r:r.update({after:r[after]+'; readingBounds=unknown'})]
            for mutate in changes:
                value=device_control();change_cleanup(value,mutate)
                with self.subTest(before=before,mutate=mutate),self.assertRaises(ValueError):self.device(value)

    def test_cleanup_requires_all_other_dom_and_native_cookie_values_to_survive(self):
        for before,after in (('beforeDomCookies','afterDomCookies'),('nativeBefore','nativeAfter')):
            changes=[lambda r:r.update({after:r[after].replace('unknown=','altered=')}),
                     lambda r:r.update({after:r[after].replace('=value','=changed')}),
                     lambda r:r.update({after:r[after]+'; invented=1'}),
                     lambda r:r.update({after:''}),lambda r:r.pop(before),lambda r:r.pop(after),
                     lambda r:r.update({before:None}),lambda r:r.update({after:True})]
            for mutate in changes:
                value=device_control();change_cleanup(value,mutate)
                with self.subTest(before=before,mutate=mutate),self.assertRaises(ValueError):self.device(value)
        value=device_control()
        def retained_unknowns(result):
            for field in ('beforeDomCookies','afterDomCookies'):
                result[field]+='; futureDom=other=opaque=value'
            for field in ('nativeBefore','nativeAfter'):
                result[field]+='; futureNative=other=opaque=value'
        change_cleanup(value,retained_unknowns);self.device(value,identity())

    def test_cleanup_requires_matching_owned_nonce_action_slot_and_unique_invocation(self):
        def reused_nonce(report):
            other=copy.deepcopy(report['eventTransport']['invocations'][0])
            other['fixtureAction']='nativeCheckpoint'
            report['eventTransport']['invocations'].append(other)
        changes=[lambda v:v.pop('eventTransport'),
                 lambda v:v['eventTransport'].update(schema=True),
                 lambda v:v['eventTransport']['buildIdentity'].update(sourceCommit='f'*40),
                 lambda v:v['eventTransport'].update(invocations=[]),
                 lambda v:v['eventTransport']['invocations'].append(copy.deepcopy(v['eventTransport']['invocations'][0])),
                 reused_nonce,
                 lambda v:v['eventTransport']['invocations'][0].update(runNonce='f'*32),
                 lambda v:v['eventTransport']['invocations'][0].update(fixtureAction='nativeCheckpoint'),
                 lambda v:v['eventTransport']['invocations'][0].update(processSlot=0),
                 lambda v:v['eventTransport']['invocations'][0].update(processSlot=True),
                 lambda v:v['eventTransport']['invocations'][0].update(events=[])]
        for mutate in changes:
            value=device_control();mutate(value)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):self.device(value)

    def test_cleanup_is_the_final_owned_event_after_optional_diagnostics(self):
        value=device_control();row=value['eventTransport']['invocations'][0]
        original=copy.deepcopy(row['events'][0])
        def record(kind,result,sequence):
            envelope=json.loads(original['rawUtf8']);envelope['sequence']=sequence
            envelope['event'].update(kind=kind,result=copy.deepcopy(result))
            raw=json.dumps(envelope,separators=(',',':'))+'\n'
            receipt=copy.deepcopy(original['receipt'])
            receipt.update(sequence=sequence,eventKind=kind,payloadBytes=len(raw.encode()),
                           payloadSha256=hashlib.sha256(raw.encode()).hexdigest())
            return dict(receipt=receipt,rawUtf8=raw)
        row['events']=[record('initialRouteReady',{'observerOffline':False},1),
                       record(CLEANUP_ACTION,value[CLEANUP_ACTION],2)]
        self.device(value,identity())
        row['events'].append(record('nativeCheckpoint',{'unrelated':True},3))
        with self.assertRaises(ValueError):self.device(value,identity())

    def test_cleanup_raw_receipt_identity_digest_sequence_and_final_result_are_checked(self):
        def mutate_raw(report,edit):
            record=report['eventTransport']['invocations'][0]['events'][0]
            envelope=json.loads(record['rawUtf8']);edit(envelope)
            record['rawUtf8']=json.dumps(envelope,separators=(',',':'))+'\n'
            raw=record['rawUtf8'].encode();record['receipt'].update(payloadBytes=len(raw),payloadSha256=hashlib.sha256(raw).hexdigest())
        changes=[lambda v:v['eventTransport']['invocations'][0]['events'][0]['receipt'].update(payloadSha256='f'*64),
                 lambda v:v['eventTransport']['invocations'][0]['events'][0]['receipt'].update(payloadBytes=1),
                 lambda v:v['eventTransport']['invocations'][0]['events'][0]['receipt'].update(command=42),
                 lambda v:v['eventTransport']['invocations'][0]['events'][0]['receipt'].update(sequence=2),
                 lambda v:v['eventTransport']['invocations'][0]['events'][0]['receipt'].update(eventKind='nativeCheckpoint'),
                 lambda v:mutate_raw(v,lambda r:r.update(runNonce='f'*32)),
                 lambda v:mutate_raw(v,lambda r:r.update(sourceCommit='f'*40)),
                 lambda v:mutate_raw(v,lambda r:r['buildIdentity'].update(apkSha256='f'*64)),
                 lambda v:mutate_raw(v,lambda r:r['event'].update(nativeContext='environment-1')),
                 lambda v:mutate_raw(v,lambda r:r['event'].update(kind='nativeCheckpoint')),
                 lambda v:mutate_raw(v,lambda r:r['event']['result'].update(invocation=42)),
                 lambda v:mutate_raw(v,lambda r:r['event']['result'].update(otherDomCookiesPreserved=False))]
        for mutate in changes:
            value=device_control();mutate(value)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):self.device(value)


class LifecycleGateImportControls(unittest.TestCase):
    def check_import_context(self, module, search_directory,import_root=ROOT):
        # Fresh interpreters prevent this file's standalone import path from
        # masking the package contexts used by staging and GitHub publication.
        source=SOURCE
        report=device_control();selected_identity=identity()
        report['sourceCommit']=source
        report['eventTransport']['buildIdentity']['sourceCommit']=source
        selected_identity['sourceCommit']=source
        report['eventTransport']['invocations']=[cleanup_transfer(report['steps'][0],selected_identity)]
        program=textwrap.dedent('''
            import copy,importlib,json,pathlib,subprocess,sys
            root=pathlib.Path(sys.argv[1]);module=sys.argv[2]
            sys.path.insert(0,str(root/sys.argv[3]))
            gate=importlib.import_module(module)
            assert gate.__package__==module.rpartition('.')[0]
            if '.' in module:
                assert str(root/'tools/gecko') not in sys.path
            value=json.load(sys.stdin);report=value['report'];identity=value['identity']
            materials=pathlib.Path(sys.argv[4])
            def selected_bytes(source,path):
                assert source==report['sourceCommit']
                if path=='third-party/sdk/geckoview-157.0.1-editable-selection.json':
                    raise FileNotFoundError('Historical counterfeit import source has no derived SDK manifest')
                relative=pathlib.PurePosixPath(path)
                assert not relative.is_absolute() and '..' not in relative.parts
                return (materials/path).read_bytes()
            def selected_git(command,**kwargs):
                assert len(command)==3 and command[:2]==['git','show']
                source,separator,path=command[2].partition(':')
                assert separator
                return selected_bytes(source,path)
            gate.selected_bytes=selected_bytes
            subprocess.check_output=selected_git
            assert gate.requires_reading_fixture_cleanup(report['sourceCommit']) is True
            invocation=gate.selected_contract(report['sourceCommit'],'profile_invocation_contract')
            decoder=gate.selected_contract(report['sourceCommit'],'integration_event_contract')
            assert invocation.__package__==decoder.__package__==gate.__package__
            invocation.verify_installed(identity,identity)
            row=report['eventTransport']['invocations'][0];record=row['events'][0]
            event=decoder.decode_event(record['receipt'],record['rawUtf8'].encode(),identity=identity,
                                       nonce=row['runNonce'],slot=1,action=row['fixtureAction'],
                                       command=report['readingFixtureCookieCleanup']['invocation'])
            assert event==report['steps'][0]
            result=gate.verify_lifecycle_device(report,report['sourceCommit'],identity)
            assert result=={'actualLifecycleDeviceAcceptance':True,'physicalPhoneAcceptance':False,
                            'actions':['copyAndReset','resetZero','deleteOne','deleteZero']}
            missing=copy.deepcopy(report);missing.pop('readingFixtureCookieCleanup')
            try:
                gate.verify_lifecycle_device(missing,report['sourceCommit'],identity)
            except ValueError:
                pass
            else:
                raise AssertionError('Capable selected source accepted a missing cleanup receipt')
            for key in ('schema','package','sourceCommit','sourceTree','dirtySource','version','versionCode',
                        'sdkCoordinate','apkSha256','apkBytes','buildStampSha256'):
                mismatched=copy.deepcopy(report)
                mismatched['eventTransport']['buildIdentity'][key]='counterfeit mismatch'
                try:
                    gate.verify_lifecycle_device(mismatched,report['sourceCommit'],identity)
                except ValueError as error:
                    assert str(error)=='Installed test APK differs from the expected build: '+key
                else:
                    raise AssertionError('Installed identity mismatch was accepted: '+key)
            print('Matched lifecycle parser and 11 installed-identity rejection controls passed')
        ''')
        completed=subprocess.run([sys.executable,'-I','-B','-c',program,str(import_root),module,search_directory,str(ROOT)],
                                 cwd='/tmp',input=json.dumps({'report':report,'identity':selected_identity}),
                                 text=True,capture_output=True)
        self.assertEqual(completed.returncode,0,completed.stdout+completed.stderr)
        self.assertEqual(completed.stdout.strip(),
                         'Matched lifecycle parser and 11 installed-identity rejection controls passed')

    def test_standalone_cli_import_retains_lifecycle_and_apk_checks(self):
        self.check_import_context('check_template_evidence','tools/gecko')

    def test_publisher_package_import_retains_lifecycle_and_apk_checks(self):
        self.check_import_context('gecko.check_template_evidence','tools')

    def test_workflow_package_import_retains_lifecycle_and_apk_checks(self):
        self.check_import_context('tools.gecko.check_template_evidence','.')

    def test_release_staged_bundle_import_retains_selected_cleanup_decoder_and_apk_checks(self):
        paths=release_stage_python_files()
        for path in (GATE_SOURCE,*CLEANUP_DEPENDENCIES):self.assertIn(path,paths)
        git_dir=subprocess.check_output(['git','rev-parse','--absolute-git-dir'],cwd=ROOT,text=True).strip()
        with tempfile.TemporaryDirectory(prefix='lifecycle-release-import-') as directory:
            stage=Path(directory)
            # Read-only Git object access mirrors a staged release checkout
            # whose source commit is available in its history.
            (stage/'.git').write_text('gitdir: '+git_dir+'\n')
            for path in paths:
                target=stage/path;target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes((ROOT/path).read_bytes())
            self.check_import_context('check_template_evidence','tools/gecko',import_root=stage)


if __name__=='__main__':unittest.main()
