#!/usr/bin/env python3
"""Actual production network core on Android, using only app-local synthetic servers."""
import argparse,json,pathlib,subprocess,time

root=pathlib.Path(__file__).resolve().parents[2];out=root/'work/gecko-integration'
p=argparse.ArgumentParser();p.add_argument('--adb',required=True);p.add_argument('--serial',default='emulator-5554');a=p.parse_args()
def adb(*args):return subprocess.check_output([a.adb,'-s',a.serial,*args],text=True,timeout=30)
adb('shell','am','force-stop','local.pocketchat.test');adb('shell','pm','clear','local.pocketchat.test');adb('logcat','-c')
adb('shell','am','start','-W','-n','local.pocketchat.test/local.pocketchat.NetworkOptimizationIntegrationActivity')
checks={}
deadline=time.monotonic()+150
while time.monotonic()<deadline:
    raw=adb('logcat','-d','-s','PocketNetworkPerformance:I','AndroidRuntime:E','*:S')
    if 'FATAL EXCEPTION' in raw:raise AssertionError(raw)
    for line in raw.splitlines():
        if 'PocketNetworkPerformance' not in line or '{' not in line:continue
        report=json.loads(line[line.index('{'):])
        if report.get("kind")=="check":
            checks[report["value"]["name"]]=report["value"];continue
        report["checks"]=list(checks.values())
        assert report["checkCount"]==len(checks),report
        report['sourceCommit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
        (out/'network-performance-results.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2),flush=True)
        assert report['status']=='passed' and report['actualAndroidExecution'] and report['actualMihomoExecution'],report
        assert len(report['checks'])>=35 and all(c['pass'] for c in report['checks']),report
        raise SystemExit(0)
    time.sleep(1)
(out/'network-performance-failure-log.txt').write_text(adb('logcat','-d'))
raise TimeoutError('No network performance result from actual Android activity')
