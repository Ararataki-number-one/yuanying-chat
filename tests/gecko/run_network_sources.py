#!/usr/bin/env python3
"""Run actual Android two-source identity and encrypted snapshot integration."""
import argparse,json,pathlib,subprocess,time
p=argparse.ArgumentParser();p.add_argument('--adb',required=True);p.add_argument('--serial',default='emulator-5554');a=p.parse_args();root=pathlib.Path(__file__).resolve().parents[2];out=root/'work/gecko-integration';out.mkdir(parents=True,exist_ok=True)
def adb(*args):return subprocess.check_output([a.adb,'-s',a.serial,*args],text=True,timeout=30)
adb('shell','am','force-stop','local.pocketchat.test');adb('shell','pm','clear','local.pocketchat.test');adb('logcat','-c');adb('shell','am','start','-W','-n','local.pocketchat.test/local.pocketchat.NetworkSourcesIntegrationActivity')
checks={};deadline=time.monotonic()+180
while time.monotonic()<deadline:
    raw=adb('logcat','-d','-s','PocketNetworkSources:I','AndroidRuntime:E','*:S')
    if 'FATAL EXCEPTION' in raw:(out/'network-source-failure-log.txt').write_text(adb('logcat','-d'));raise AssertionError(raw)
    for line in raw.splitlines():
        if 'PocketNetworkSources' not in line or '{' not in line:continue
        report=json.loads(line[line.index('{'):])
        if report.get('kind')=='check':checks[report['value']['name']]=report['value'];continue
        if report.get('kind')!='result':continue
        report['checks']=list(checks.values())
        report['sourceCommit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip();(out/'network-source-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
        if report['status']!='passed':(out/'network-source-failure-log.txt').write_text(adb('logcat','-d'))
        assert len(report['coreSha256'])==64 and report['coreVersion'] and report['coreAbi'] in ('x86_64','arm64-v8a')
        assert report['status']=='passed' and report['actualAndroidExecution'] and report['actualNativeExecution'] and report['actualKeystoreEncryption']
        assert not report['actualRouteApplication'] and report['checkCount']==len(report['checks'])>=44 and all(c['pass'] for c in report['checks'])
        raise SystemExit(0)
    time.sleep(1)
(out/'network-source-failure-log.txt').write_text(adb('logcat','-d'));raise TimeoutError('No Android source integration result')
