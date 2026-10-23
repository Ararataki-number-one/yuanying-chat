"""Counterfeit counter records for gate rejection tests, never device evidence."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from gecko.check_interaction_transfer_evidence import verify_display_sampling

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
    return dict(actualMihomoExecution=True,checks=[dict(name=n,pass_=True) for n in NAMES],
                initialDisplaySampling=dict(busyRequests=2,idleRequests=2),
                telemetryScheduling=dict(queuedBusyRequests=2,idleSampleRequests=2,newerSampleDuplicateRequests=0,
                    recoveryExitRequests=1,webSocketConnections=1,webSocketEchoes=4))

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
                if change=='missing':report['checks'].pop()
                elif change=='failed':report['checks'][0]['pass']=False
                else:report['actualMihomoExecution']=False
                with self.assertRaises(AssertionError):verify_display_sampling(report)

if __name__=='__main__':unittest.main()
