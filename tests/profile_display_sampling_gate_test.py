"""Counterfeit counter records for gate rejection tests, never device evidence."""
import copy
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from gecko.check_interaction_transfer_evidence import verify_display_sampling, verify_read_model_freshness, READ_MODEL_CASES, verify_read_model_identity, READ_MODEL_IDENTITY_CASES, identity_projection_fixture

NAMES=[
    'Automatic display sampling measures the current route while a reply is busy',
    'A fresh busy-route sample is reused after the reply becomes idle',
    'Queued automatic sampling measures without interrupting the newly busy reply',
    'The queued busy sample remains fresh when the reply becomes idle',
    'Queued display sampling reuses a newer same-route health sample instead of probing twice',
    'Automatic telemetry scheduling preserves one WebSocket and the exact core identity',
    'Actual failed-chain recovery performs exactly one full exit verification for the new entry',
    'Removing duplicate recovery verification preserves the live WebSocket and fixed exit',
]
def metadata():
    value=dict(actualMihomoExecution=True,checks=[dict(name=n,pass_=True) for n in NAMES],
                initialDisplaySampling=dict(busyRequests=2,idleRequests=2),
                telemetryScheduling=dict(queuedBusyRequests=2,idleSampleRequests=2,newerSampleDuplicateRequests=0,
                    recoveryExitRequests=1,webSocketConnections=1,webSocketEchoes=4))
    row=dict(slot=0,name='controlled read model',environmentId='controlled-model-environment',generation=2)
    cases=[]
    for name,now,at,live,state,connected in READ_MODEL_CASES:
        runtime=dict(environmentId=row['environmentId'],generation=2,mode='external',configured=True,connected=True,
                     route='controlled-route',delayRoute='controlled-route',delay=42,delayAt=now,delayKind='response',latencyRemaining=120000,ip='192.0.2.42')
        if at is not None:runtime['at']=at
        if name=='wrong-uuid':runtime['environmentId']='another-environment'
        if name=='wrong-generation':runtime['generation']=3
        if name.endswith('reported-issue'):runtime['issue']='controlled reported issue'
        if name=='fresh-blocked-exit':runtime['blocked']=True
        foreign=name in ('wrong-uuid','wrong-generation');latency='延迟未测' if foreign else '42 ms' if connected else '42 ms（上次）'
        cases.append(dict(case=name,now=now,live=live,input=runtime,state=state,connected=connected,latency=latency,
                          timer='（02:00）' if connected or name=='fresh-reported-issue' else '（等待连接）',
                          mainline='地区未标注 · IP 未核验 · 延迟未测' if foreign else '地区未标注 · '+('' if connected else '上次 ')+'192.0.2.42 · '+latency,inputUnchanged=True))
        value['checks'].append(dict(name='Android read-model freshness '+name,pass_=True))
    value['networkReadModelFreshness']=dict(schema=1,scope='controlled Android read-model projection; no IPC ownership, live route or real latency claim',row=row,cases=cases)
    summary={key:item for key,item in value['networkReadModelFreshness'].items() if key!='cases'}
    for check,case in zip(value['checks'][len(NAMES):],cases):check.update(readModel=copy.deepcopy(case),readModelSummary=copy.deepcopy(summary))
    identity_cases=[]
    for name in READ_MODEL_IDENTITY_CASES:
        identity_summary,case=identity_projection_fixture(name);identity_cases.append(case)
        value['checks'].append(dict(name='Android read-model identity '+name,pass_=True,readModel=copy.deepcopy(case),readModelSummary=copy.deepcopy(identity_summary)))
    value['networkReadModelIdentity']=dict(identity_summary,cases=identity_cases)
    return value

class DisplayGateTest(unittest.TestCase):
    def fixture(self):
        value=metadata()
        for check in value['checks']:check['pass']=check.pop('pass_')
        return value
    def test_new_counts_still_require_exact_reuse_and_socket_continuity(self):
        verify_display_sampling(self.fixture())
    def test_reject_old_busy_skips_duplicate_requests_or_broken_continuity(self):
        for group,key,value in [
            ('initialDisplaySampling','busyRequests',0),('initialDisplaySampling','idleRequests',4),
            ('telemetryScheduling','queuedBusyRequests',0),('telemetryScheduling','queuedBusyRequests',4),
            ('telemetryScheduling','idleSampleRequests',4),('telemetryScheduling','newerSampleDuplicateRequests',2),
            ('telemetryScheduling','recoveryExitRequests',2),('telemetryScheduling','webSocketConnections',2),
            ('telemetryScheduling','webSocketEchoes',0),('telemetryScheduling','recoveryExitRequests',True),
        ]:
            with self.subTest(group=group,key=key,value=value):
                report=self.fixture();report[group][key]=value
                with self.assertRaises(AssertionError):verify_display_sampling(report)
        for change in ('missing','failed','noNative'):
            with self.subTest(change=change):
                report=self.fixture()
                if change=='missing':report['checks']=[c for c in report['checks'] if c['name']!=NAMES[-1]]
                elif change=='failed':report['checks'][0]['pass']=False
                else:report['actualMihomoExecution']=False
                with self.assertRaises(AssertionError):verify_display_sampling(report)

    def test_read_model_projection_rejects_missing_duplicate_or_relabelled_cases(self):
        for change in ('missing-report','missing-case','duplicate','old-label','claimed-current','countdown','wrong-time','wrong-identity','changed-input','real-latency-claim','bool-schema','other-check-reading','other-check-summary'):
            with self.subTest(change=change):
                report=self.fixture();projection=report['networkReadModelFreshness'];case=projection['cases'][2]
                if change=='missing-report':del report['networkReadModelFreshness']
                elif change=='missing-case':projection['cases'].pop()
                elif change=='duplicate':projection['cases'][2]=copy.deepcopy(projection['cases'][1])
                elif change=='old-label':case['state']='未运行'
                elif change=='claimed-current':case['connected']=True
                elif change=='countdown':case['timer']='（02:00）'
                elif change=='wrong-time':case['input']['at']+=1
                elif change=='wrong-identity':case['input']['environmentId']='other'
                elif change=='changed-input':case['inputUnchanged']=False
                elif change=='real-latency-claim':projection['scope']='actual route latency'
                elif change=='bool-schema':projection['schema']=True
                elif change=='other-check-reading':report['checks'][-1]['readModel']['state']='正常'
                else:report['checks'][-1]['readModelSummary']['scope']='other invocation'
                with self.assertRaises((AssertionError,KeyError)):verify_display_sampling(report)

    def test_each_required_device_projection_check_is_compulsory(self):
        for name, *_ in READ_MODEL_CASES:
            with self.subTest(name=name):
                report=self.fixture();report['checks']=[c for c in report['checks'] if c['name']!='Android read-model freshness '+name]
                with self.assertRaises(AssertionError):verify_display_sampling(report)

    def test_foreign_identity_values_are_retained_raw_without_being_required_as_trusted_history(self):
        report=self.fixture()
        for case in report['networkReadModelFreshness']['cases']:
            if case['case'] in ('wrong-uuid','wrong-generation'):
                case['latency']='延迟未测';case['mainline']='地区未标注 · IP 未核验 · 延迟未测'
                check=next(item for item in report['checks'] if item['name']=='Android read-model freshness '+case['case'])
                check['readModel']=copy.deepcopy(case)
        verify_display_sampling(report)

    def replay_collector(self,report,out,raw):
        tree=ast.parse((Path(__file__).resolve().parent/'gecko/run_network_performance.py').read_bytes())
        assignment=next(node for node in ast.walk(tree) if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='model_checks' for target in node.targets))
        branch=next(node for node in ast.walk(tree) if isinstance(node,ast.If) and isinstance(node.test,ast.Name) and node.test.id=='model_checks')
        program=compile(ast.Module(body=[assignment,branch],type_ignores=[]),'<actual Android projection collector>','exec')
        environment=dict(report=report,checks={check['name']:check for check in report['checks']},out=out,raw=raw)
        exec(program,environment)

    def test_actual_runner_collector_reconstructs_same_checked_projection(self):
        with tempfile.TemporaryDirectory() as directory:
            report=self.fixture();del report['networkReadModelFreshness']
            self.replay_collector(report,Path(directory),'controlled log')
            verify_display_sampling(report)
            self.assertFalse((Path(directory)/'network-performance-failure-log.txt').exists())

    def test_actual_runner_collector_preserves_raw_mixed_summary_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            report=self.fixture();del report['networkReadModelFreshness'];[check for check in report['checks'] if check['name'].startswith('Android read-model freshness ')][-1]['readModelSummary']['scope']='other invocation'
            with self.assertRaises(AssertionError):self.replay_collector(report,Path(directory),'original controlled failure log')
            self.assertEqual((Path(directory)/'network-performance-failure-log.txt').read_text(),'original controlled failure log')

    def replay_check_snapshot(self,events,checks,out,raw):
        tree=ast.parse((Path(__file__).resolve().parent/'gecko/run_network_performance.py').read_bytes())
        reset=next(node for node in ast.walk(tree) if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='model_snapshot' for target in node.targets))
        branch=next(node for node in ast.walk(tree) if isinstance(node,ast.If) and isinstance(node.test,ast.Compare) and any(isinstance(value,ast.Constant) and value.value=='check' for value in node.test.comparators))
        loop=ast.For(target=ast.Name(id='report',ctx=ast.Store()),iter=ast.Name(id='events',ctx=ast.Load()),body=[branch],orelse=[])
        program=compile(ast.fix_missing_locations(ast.Module(body=[reset,loop],type_ignores=[])),'<actual per-snapshot check guard>','exec')
        exec(program,dict(events=events,checks=checks,out=out,raw=raw))

    def test_actual_runner_allows_identical_repeated_polls_without_recounting(self):
        with tempfile.TemporaryDirectory() as directory:
            report=self.fixture();events=[dict(kind='check',value=check) for check in report['checks']];checks={}
            self.replay_check_snapshot(events,checks,Path(directory),'first poll')
            self.replay_check_snapshot(copy.deepcopy(events),checks,Path(directory),'same records on next poll')
            self.assertEqual(len(checks),len(report['checks']))
            self.assertFalse((Path(directory)/'network-performance-failure-log.txt').exists())

    def test_actual_runner_rejects_new_case_duplicates_before_dictionary_overwrite(self):
        for conflict in (False,True):
            with self.subTest(conflict=conflict),tempfile.TemporaryDirectory() as directory:
                report=self.fixture();events=[dict(kind='check',value=copy.deepcopy(check)) for check in report['checks']]
                repeated=copy.deepcopy(events[len(NAMES)])
                if conflict:repeated['value']['pass']=False
                events.insert(len(NAMES),repeated)
                raw='original false-before-true raw' if conflict else 'original duplicate raw'
                with self.assertRaises(AssertionError):self.replay_check_snapshot(events,{},Path(directory),raw)
                self.assertEqual((Path(directory)/'network-performance-failure-log.txt').read_text(),raw)

    def test_actual_runner_rejects_conflicting_new_case_across_polls(self):
        with tempfile.TemporaryDirectory() as directory:
            value=self.fixture()['checks'][len(NAMES)];failed=copy.deepcopy(value);failed['pass']=False;checks={}
            self.replay_check_snapshot([dict(kind='check',value=failed)],checks,Path(directory),'first failed observation')
            with self.assertRaises(AssertionError):self.replay_check_snapshot([dict(kind='check',value=value)],checks,Path(directory),'later contradictory observation')
            self.assertEqual((Path(directory)/'network-performance-failure-log.txt').read_text(),'later contradictory observation')

    def test_original_non_projection_check_dictionary_behavior_is_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            checks={};events=[dict(kind='check',value={'name':NAMES[0],'pass':value}) for value in (False,True)]
            self.replay_check_snapshot(events,checks,Path(directory),'original non-model events')
            self.assertIs(checks[NAMES[0]]['pass'],True)

    def test_identity_projection_requires_every_case_check_and_original_scope(self):
        verify_read_model_identity(self.fixture())
        for change in ('missing-report','missing-case','duplicate','order','scope','row','config','schema','missing-check','failed-check','duplicate-check'):
            with self.subTest(change=change):
                report=self.fixture();projection=report['networkReadModelIdentity']
                if change=='missing-report':del report['networkReadModelIdentity']
                elif change=='missing-case':projection['cases'].pop()
                elif change=='duplicate':projection['cases'][1]=copy.deepcopy(projection['cases'][0])
                elif change=='order':projection['cases'].reverse()
                elif change=='scope':projection['scope']='actual route'
                elif change=='row':projection['row']['environmentId']='another'
                elif change=='config':projection['config']['entry']='changed'
                elif change=='schema':projection['schema']=True
                elif change=='missing-check':report['checks'].pop()
                elif change=='failed-check':report['checks'][-1]['pass']=False
                else:report['checks'].append(copy.deepcopy(report['checks'][-1]))
                with self.assertRaises((AssertionError,KeyError)):verify_read_model_identity(report)

    def test_identity_projection_rejects_changed_raw_inputs_or_projected_runtime(self):
        for field,value in [('now',True),('live',1),('inputUnchanged',False),('input',{}),('output',{})]:
            with self.subTest(field=field):
                report=self.fixture();case=report['networkReadModelIdentity']['cases'][0];case[field]=value
                report['checks'][-len(READ_MODEL_IDENTITY_CASES)]['readModel']=copy.deepcopy(case)
                with self.assertRaises(AssertionError):verify_read_model_identity(report)
        for field,value in [('latency','42 ms（上次）'),('ip','192.0.2.42'),('region','Foreign region'),('runtime',{'connected':True})]:
            with self.subTest(field=field):
                report=self.fixture();case=report['networkReadModelIdentity']['cases'][4];case['output'][field]=value
                report['checks'][-len(READ_MODEL_IDENTITY_CASES)+4]['readModel']=copy.deepcopy(case)
                with self.assertRaises(AssertionError):verify_read_model_identity(report)

    def test_nested_foreign_configuration_cannot_reappear_in_the_public_projection(self):
        for index in (-2,-1):
            report=self.fixture();case=report['networkReadModelIdentity']['cases'][index]
            case['output']['runtime']['runningConfiguration']=copy.deepcopy(case['input']['runningConfiguration'])
            report['checks'][index]['readModel']=copy.deepcopy(case)
            with self.assertRaises(AssertionError):verify_read_model_identity(report)

    def replay_identity_collector(self,report,out,raw):
        tree=ast.parse((Path(__file__).resolve().parent/'gecko/run_network_performance.py').read_bytes())
        assignment=next(node for node in ast.walk(tree)if isinstance(node,ast.Assign)and any(isinstance(target,ast.Name)and target.id=='identity_checks'for target in node.targets))
        branch=next(node for node in ast.walk(tree)if isinstance(node,ast.If)and isinstance(node.test,ast.Name)and node.test.id=='identity_checks')
        program=compile(ast.Module(body=[assignment,branch],type_ignores=[]),'<actual Android identity collector>','exec')
        exec(program,dict(report=report,checks={check['name']:check for check in report['checks']},out=out,raw=raw))

    def test_actual_identity_collector_reconstructs_original_projection(self):
        with tempfile.TemporaryDirectory()as name:
            report=self.fixture();del report['networkReadModelIdentity']
            self.replay_identity_collector(report,Path(name),'original synthetic identity log')
            verify_display_sampling(report)

    def test_actual_identity_collector_retains_mixed_summary_failure_log(self):
        with tempfile.TemporaryDirectory()as name:
            report=self.fixture();del report['networkReadModelIdentity'];report['checks'][-1]['readModelSummary']['scope']='other invocation'
            with self.assertRaises(AssertionError):self.replay_identity_collector(report,Path(name),'original mixed identity log')
            self.assertEqual((Path(name)/'network-performance-failure-log.txt').read_text(),'original mixed identity log')

    def test_actual_snapshot_guard_rejects_duplicate_identity_cases(self):
        for conflict in (False,True):
            with self.subTest(conflict=conflict),tempfile.TemporaryDirectory()as name:
                report=self.fixture();events=[dict(kind='check',value=copy.deepcopy(check))for check in report['checks']]
                repeated=copy.deepcopy(events[-1])
                if conflict:repeated['value']['pass']=False
                events.append(repeated)
                with self.assertRaises(AssertionError):self.replay_check_snapshot(events,{},Path(name),'original duplicate identity log')
                self.assertEqual((Path(name)/'network-performance-failure-log.txt').read_text(),'original duplicate identity log')

    def test_original_producers_presentation_rules_and_network_checks_are_preserved(self):
        root=Path(__file__).resolve().parents[1]
        spec=importlib.util.spec_from_file_location('identity_source_preservation',root/'tests/chrome-network-state-host/run.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        source=(root/'app/src/main/java/local/pocketchat/WindowNetworkState.java').read_text()
        hashes={
            'static JSONObject running(':'a4109d3648dc4c24b2ce7f0b7bece8a76d7b02a3fe454bbb0cb450c053dea51c',
            'static JSONObject live(':'72d6092fa68265d84ba6f0229d23fa721f811fa20173ef0fadbc126d7a5b5938',
            'static WindowNetworkState current(':'8fcff52eb8a56c5ea5c47741f63ce3d8fcc8a254d11f22042214ab6d0c908a7c',
            'static JSONArray windows(':'6cf4363876c70674a419375454de6d60c9d5a282064762f66484fa342e932a95',
            'static synchronized void save(':'67e3713bf07b69deee0ff1c2529f7b4b3e8260f9a38428016688620ef7981705',
            'String mainline(':'798146f5664819b9159752da620515b28d064f8388c323384866bf2128619053',
            'String strip(':'81ae15a4415223931b9f00cb8be5dfe901b14535dfabf8d9d54c6e763336a7a0',
            'String subline(':'5295cf5770dec8a7ef956fa48b0d894283b9abd2621882565aca4a1f503aba62',
            'int color(':'a35d0ca4ec871037d75bb4e27021f915b99354a81f4179fd9d0f57885bdbed62',
        }
        for needle,digest in hashes.items():
            with self.subTest(needle=needle):self.assertEqual(hashlib.sha256(module.member(source,needle).encode()).hexdigest(),digest)
        fixture=(root/'tests/gecko/NetworkOptimizationIntegrationActivity.java').read_text()
        names=re.findall(r'check\("([^"\n]+)"',fixture)
        self.assertEqual(len(names),166)
        self.assertEqual(hashlib.sha256(json.dumps(names,separators=(',',':')).encode()).hexdigest(),'637a695a29e642cccbb58a2f19507707116a1556091cd492bdc62f37e7f4367e')

    def test_host_wiring_only_adds_two_identity_commands_to_the_original_workflow(self):
        root=Path(__file__).resolve().parents[1];source=(root/'.github/workflows/gecko-integration.yml').read_text()
        for jar,label in [('catalog-json.jar','desktop'),('sharing-android-json.jar','android')]:
            line='        python3 tests/window-network-identity-host/run.py --java-home "$JAVA_HOME" --json-jar work/gecko-integration/'+jar+' --output work/gecko-integration/window-network-identity-'+label+'-host-results.json\n'
            self.assertEqual(source.count(line),1);source=source.replace(line,'')
        # The independently reviewed R02 fixture adds this exact invocation.
        # Invert only that insertion before checking the unchanged d341 workflow.
        binding='        if ! python3 tests/gecko/run_network_client_binding.py --adb "$(command -v adb)" --serial emulator-5554; then\n          checks_failed=1\n        fi\n'
        self.assertEqual(source.count(binding),1);source=source.replace(binding,'',1)
        self.assertEqual(hashlib.sha256(source.encode()).hexdigest(),'50fdca828ab3f661aff423bf6755359d2f4e8b24c3e78e0100d8ce29da8120c1')

    def test_actual_identity_runner_rejects_partial_or_failed_93_and_14_reports(self):
        source=Path(__file__).resolve().parent/'window-network-identity-host/run.py';tree=ast.parse(source.read_text())
        guards=[node for node in ast.walk(tree)if isinstance(node,ast.If)and ("report.get('total') != 93"in ast.unparse(node.test)or"projection.get('total') != 14"in ast.unparse(node.test))]
        self.assertEqual(len(guards),2);program=compile(ast.Module(body=guards,type_ignores=[]),'<actual 93/14 runner guards>','exec')
        def value(count):return dict(status='passed',passed=count,total=count,checks=[{'pass':True}for _ in range(count)])
        for change in ('none','93-count','93-missing','93-bool','93-false','14-count','14-missing','14-bool','14-false','14-exit'):
            report,projection=value(93),value(14);code=0
            if change=='93-count':report['passed']=0
            if change=='93-missing':report['checks']=[]
            if change=='93-bool':report['total']=True
            if change=='93-false':report['checks'][0]['pass']=False
            if change=='14-count':projection['passed']=0
            if change=='14-missing':projection['checks']=[]
            if change=='14-bool':projection['total']=True
            if change=='14-false':projection['checks'][0]['pass']=False
            if change=='14-exit':code=1
            from types import SimpleNamespace
            exec(program,dict(report=report,projection=projection,projected=SimpleNamespace(returncode=code)))
            self.assertEqual(report['status']=='passed',change=='none',change)

if __name__=='__main__':unittest.main()
