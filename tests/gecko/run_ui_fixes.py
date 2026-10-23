#!/usr/bin/env python3
"""Actual SDK extension replacement and real two-minute local-chain probe cadence."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'work/gecko-integration'

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--adb', required=True)
    p.add_argument('--serial', default='emulator-5554')
    args = p.parse_args()
    def adb(*parts):
        return subprocess.run([args.adb, '-s', args.serial, *parts], text=True,
                              capture_output=True, timeout=40, check=True).stdout
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    apk = ROOT/'app/build/outputs/apk/integration/app-x86_64-integration.apk'
    apk_hash = hashlib.sha256(apk.read_bytes()).hexdigest()
    cases = [('ExtensionUpgradeIntegrationActivity', 'extension-upgrade', 75),
             ('PeriodicLatencyIntegrationActivity', 'periodic-latency', 180)]
    OUT.mkdir(parents=True, exist_ok=True)
    failures=[]
    for activity, key, timeout in cases:
        target = OUT/(key+'-results.json')
        target.unlink(missing_ok=True)
        adb('shell', 'am', 'force-stop', 'local.pocketchat.test')
        adb('shell', 'pm', 'clear', 'local.pocketchat.test')
        adb('logcat', '-c')
        adb('shell', 'am', 'start', '-W', '-n', 'local.pocketchat.test/local.pocketchat.'+activity)
        deadline = time.monotonic()+timeout
        try:
            while time.monotonic()<deadline:
                raw = subprocess.run([args.adb, '-s', args.serial, 'exec-out', 'content', 'read',
                                      '--uri', 'content://local.pocketchat.test.evidence/'+key],
                                     capture_output=True, text=True, timeout=40).stdout
                if raw.lstrip().startswith('{'):
                    report = json.loads(raw)
                    target.write_text(json.dumps(report, indent=2)+'\n')
                    assert report['status']=='passed', report
                    assert report['actualAndroidExecution'] is True
                    assert report['realChatGptAcceptance'] is False
                    identity = report['buildIdentity']
                    assert identity['sourceCommit']==source and identity['apkSha256']==apk_hash, identity
                    assert report['checks'] and all(c['pass'] for c in report['checks']), report
                    if key=='extension-upgrade':
                        manifest=json.loads((ROOT/'app/src/main/assets/gecko/manifest.json').read_text())
                        assert report['expectedVersion']==manifest['version'] and len(report['checks'])==5
                    else:
                        assert 119000<=report['elapsedMs']<135000 and len(report['checks'])==7
                        heads=[e for e in report['wire'] if e['kind']=='head' and e['path']=='/periodic']
                        assert len(heads)==4 and heads[2]['at']-heads[0]['at']>=119000, heads
                    print(json.dumps({'test':key,'status':'passed','checks':len(report['checks'])}), flush=True)
                    break
                time.sleep(1)
            else:
                raise TimeoutError('No complete report for '+key)
        except Exception as failure:
            failures.append((key,str(failure)))
        finally:
            (OUT/(key+'-log.txt')).write_text(adb('logcat', '-d'))
    if failures:raise AssertionError(failures)

if __name__=='__main__':
    main()
