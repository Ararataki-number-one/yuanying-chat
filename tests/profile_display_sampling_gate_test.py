"""Counterfeit counter records for gate rejection tests, never device evidence."""
import copy
import ast
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from gecko.check_interaction_transfer_evidence import verify_display_sampling, verify_read_model_freshness, READ_MODEL_CASES

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
        latency='42 ms' if connected else '42 ms（上次）'
        cases.append(dict(case=name,now=now,live=live,input=runtime,state=state,connected=connected,latency=latency,
                          timer='（02:00）' if connected or name=='fresh-reported-issue' else '（等待连接）',
                          mainline='地区未标注 · '+('' if connected else '上次 ')+'192.0.2.42 · '+latency,inputUnchanged=True))
        value['checks'].append(dict(name='Android read-model freshness '+name,pass_=True))
    value['networkReadModelFreshness']=dict(schema=1,scope='controlled Android read-model projection; no IPC ownership, live route or real latency claim',row=row,cases=cases)
    summary={key:item for key,item in value['networkReadModelFreshness'].items() if key!='cases'}
    for check,case in zip(value['checks'][len(NAMES):],cases):check.update(readModel=copy.deepcopy(case),readModelSummary=copy.deepcopy(summary))
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
            report=self.fixture();del report['networkReadModelFreshness'];report['checks'][-1]['readModelSummary']['scope']='other invocation'
            with self.assertRaises(AssertionError):self.replay_collector(report,Path(directory),'original controlled failure log')
            self.assertEqual((Path(directory)/'network-performance-failure-log.txt').read_text(),'original controlled failure log')

if __name__=='__main__':unittest.main()
