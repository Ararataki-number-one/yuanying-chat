#!/usr/bin/env python3
"""Actual production network core on Android, using only app-local synthetic servers."""
import argparse,json,pathlib,subprocess,sys,time

root=pathlib.Path(__file__).resolve().parents[2];out=root/'work/gecko-integration'
sys.path.insert(0,str(root))
from tools.gecko.check_connection_evidence import verify_detector_transport_evidence, verify_network_repair_evidence
p=argparse.ArgumentParser();p.add_argument('--adb',required=True);p.add_argument('--serial',default='emulator-5554');a=p.parse_args()
def adb(*args):return subprocess.check_output([a.adb,'-s',a.serial,*args],text=True,timeout=30)
adb('shell','am','force-stop','local.pocketchat.test');adb('shell','pm','clear','local.pocketchat.test');adb('logcat','-c')
adb('shell','am','start','-W','-n','local.pocketchat.test/local.pocketchat.NetworkOptimizationIntegrationActivity')
checks={};transport_evidence={};first_connection_diagnostic=None
deadline=time.monotonic()+240
while time.monotonic()<deadline:
    raw=adb('logcat','-d','-s','PocketNetworkPerformance:I','AndroidRuntime:E','*:S')
    if 'FATAL EXCEPTION' in raw:
        (out/'network-performance-failure-log.txt').write_text(adb('logcat','-d'))
        raise AssertionError(raw)
    for line in raw.splitlines():
        if 'PocketNetworkPerformance' not in line or '{' not in line:continue
        try:report=json.loads(line[line.index('{'):])
        except json.JSONDecodeError:
            # Preserve the exact observed bytes before requesting the full log.
            (out/'network-performance-unparsed-log.txt').write_text(raw)
            (out/'network-performance-failure-log.txt').write_text(adb('logcat','-d'))
            raise
        if report.get("kind")=="check":
            checks[report["value"]["name"]]=report["value"];continue
        if report.get('kind')=='exitTransportEvidence':
            value=report['value'];transport_evidence[(value['kind'],value['fault'])]=value;continue
        if report.get('kind')=='firstConnectionDiagnostic':
            first_connection_diagnostic=report['value']
            (out/'network-first-connection-diagnostic.json').write_text(json.dumps(first_connection_diagnostic,indent=2)+'\n')
            continue
        report["checks"]=list(checks.values())
        report['exitTransportContinuity']=list(transport_evidence.values())
        if first_connection_diagnostic is not None:report['firstConnectionDiagnostic']=first_connection_diagnostic
        assert report["checkCount"]==len(checks),report
        report['sourceCommit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
        (out/'network-performance-results.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2),flush=True)
        if report['status']!='passed':(out/'network-performance-failure-log.txt').write_text(adb('logcat','-d'))
        assert report['status']=='passed' and report['actualAndroidExecution'] and report['actualMihomoExecution'],report
        assert len(report['checks'])>=143 and all(c['pass'] for c in report['checks']),report
        verify_detector_transport_evidence(report)
        verify_network_repair_evidence(report)
        raise SystemExit(0)
    time.sleep(1)
(out/'network-performance-failure-log.txt').write_text(adb('logcat','-d'))
raise TimeoutError('No network performance result from actual Android activity')
