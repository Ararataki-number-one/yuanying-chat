#!/usr/bin/env python3
"""Verify real Android notification channels and production service behavior."""
import argparse,json,pathlib,subprocess,time

root=pathlib.Path(__file__).resolve().parents[2]
out=root/'work/gecko-integration'
p=argparse.ArgumentParser();p.add_argument('--adb',required=True);p.add_argument('--serial',required=True);args=p.parse_args()
def adb(*values):return subprocess.check_output([args.adb,'-s',args.serial,*values],text=True,timeout=30)
package='local.pocketchat.test'
adb('shell','am','force-stop',package);adb('shell','pm','clear',package)
if int(adb('shell','getprop','ro.build.version.sdk').strip())>=33:adb('shell','pm','grant',package,'android.permission.POST_NOTIFICATIONS')
adb('logcat','-c')
adb('shell','am','start','-W','-n',package+'/local.pocketchat.NotificationQuietIntegrationActivity')
checks={};home_sent=False;deadline=time.monotonic()+120
try:
    while time.monotonic()<deadline:
        raw=adb('logcat','-d','-s','PocketQuietNotifications:I','AndroidRuntime:E','*:S')
        assert 'FATAL EXCEPTION' not in raw,raw
        for line in raw.splitlines():
            if 'PocketQuietNotifications' not in line or '{' not in line:continue
            result=json.loads(line[line.index('{'):])
            if result.get('kind')=='check':checks[result['value']['name']]=result['value'];continue
            if result.get('kind')=='homeNeeded':
                if not home_sent:adb('shell','input','keyevent','KEYCODE_HOME');home_sent=True
                continue
            result['checks']=list(checks.values())
            result['sourceCommit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
            (out/'quiet-notification-results.json').write_text(json.dumps(result,indent=2)+'\n')
            print(json.dumps(result,indent=2),flush=True)
            assert result['status']=='passed' and result['actualAndroidExecution'] and result['checkCount']==len(checks) and len(checks)>=10 and all(c['pass'] for c in result['checks']),result
            raise SystemExit(0)
        time.sleep(1)
    raise TimeoutError('No notification regression result from Android')
except Exception:
    (out/'quiet-notification-failure-log.txt').write_text(adb('logcat','-d'))
    raise
