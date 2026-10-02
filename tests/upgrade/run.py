"""Use only emulator-5554: install each baseline, seed fixtures, then update without clearing data."""
import hashlib,json,pathlib,subprocess,time
repo=pathlib.Path(__file__).resolve().parents[2]
adb=[str(repo/'work/cloud-setup/adb/platform-tools/adb'),'-s','emulator-5554']
out=repo/'work/upgrade-qa/results';out.mkdir(parents=True,exist_ok=True)
current=repo/'dist/PocketChat-1.5.1.apk'
baselines=[('original-v1.5.0',repo/'work/signature-check/YuanyingChat-v1.5.0-original.apk'),('previous-original-signed-preview',repo/'dist/PocketChat-1.5.0-environment-preview-original-signature.apk')]
def run(*args,required=True,timeout=300):
    r=subprocess.run(adb+list(map(str,args)),capture_output=True,text=True,timeout=timeout)
    if required and (r.returncode or 'Error:' in r.stdout or 'Failure [' in r.stdout):
        raise RuntimeError('adb operation failed: '+r.stdout+r.stderr)
    return r.stdout
assert run('shell','getprop','ro.kernel.qemu').strip()=='1','Disposable emulator required'
run('install','-r','--no-streaming',repo/'work/upgrade-qa/upgrade-fixture.apk')
summary=[]
for label,baseline in baselines:
    assert baseline.exists(),str(baseline)
    print('Upgrade baseline:',label,flush=True)
    run('uninstall','local.pocketchat',required=False)
    run('install','--no-streaming',baseline)
    for phase in ['seed','verify']:
        if phase=='verify':
            print('Updating installed baseline without uninstalling or clearing data',flush=True)
            assert 'Success' in run('install','-r','--no-streaming',current)
        raw=run('shell','am','instrument','-w','-r','-e','phase',phase,'-e','baseline',label,'-e','allowFixtureWrites','true','local.pocketchat.upgradeqa/local.pocketchat.upgradeqa.UpgradeRegression',timeout=480)
        (out/(label+'-'+phase+'.txt')).write_text(raw)
        lines=[line[len('INSTRUMENTATION_RESULT: results='):] for line in raw.splitlines() if line.startswith('INSTRUMENTATION_RESULT: results=')]
        assert lines,raw
        data=json.loads(lines[0]);(out/(label+'-'+phase+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
        checks=data.get('checks',[]);bad=[row for row in checks if row.get('pass') is not True]
        print(phase,len(checks)-len(bad),'/',len(checks),'passed',flush=True)
        assert checks and not bad and not data.get('error'),data
        if phase=='verify': summary.append({'baseline':label,'apk_sha256':hashlib.sha256(current.read_bytes()).hexdigest(),'checks':len(checks),'passed':len(checks)})
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
