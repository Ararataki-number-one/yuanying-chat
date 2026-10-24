"""Synthetic parser inputs only; no claim of signing, installation or device work."""
import copy
import hashlib
import json
from pathlib import Path
from native_input_signature_fixture import signature_files


def raw(value):
    return (json.dumps(value, sort_keys=True) + '\n').encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def add_file(report, root, name, value):
    data = value if type(value) is bytes else raw(value)
    path = Path(root) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    report.setdefault('rawEvidence', [])[:] = [r for r in report.get('rawEvidence', []) if r['path'] != name]
    report['rawEvidence'].append(dict(path=name, bytes=len(data), sha256=digest(data)))
    return data


def attach_driver(module, report, build, protocol, root):
    n = module.native_input
    build.update(runId='901', runAttempt='1')
    compiled = dict(schema=1, status='built',compileOnly=False,testOnly=True,
        sourceCommit=build['sourceCommit'], sourceTree=build['sourceTree'],
        runId='901', runAttempt='1', packageName=n.SELF, targetPackage=n.TARGET,
        instrumentationTargetPackage=n.SELF, instrumentation=n.SELF + '.NativeInputInstrumentation',
        executionBackend='shell-input-manager-global-v1', entryPoint=n.SELF + '.NativeInputShell',
        executionUid=2000, inputTargetUidEnforced=True,
        protocols=copy.deepcopy(n.PROTOCOLS), inputs={name: protocol[name] for name in n.INPUTS},
        signerCertificateSha256='7'*64, apkSha256='8'*64, apkBytes=80)
    signing = signature_files(compiled, protocol[n.SIGNATURE_VERIFIER])
    compiled_raw = raw(compiled)
    build['nativeInputDriver'] = dict(build=compiled, apkSha256=compiled['apkSha256'], apkBytes=80,
        receiptSha256=digest(compiled_raw), signerCertificateSha256=compiled['signerCertificateSha256'])
    proof = dict(schema=1, status='verified-bytes', actualInstalledApkRead=True,
        compiledFileFallback=False, retryPerformed=False, returnCode=0,
        transport='adb-shell-v2-no-pty-ranged', dataSource='binary-stdout-destination-file',
        actualFileSha256=build['apkSha256'], stdoutSha256=build['apkSha256'], expectedSha256=build['apkSha256'],
        actualFileBytes=build['apkBytes'], stdoutBytes=build['apkBytes'], expectedBytes=build['apkBytes'],
        rangeBytes=4194304, ranges=[dict(index=0, offset=0, actualBytes=build['apkBytes'],
            expectedBytes=build['apkBytes'], returnCode=0, status='verified-length', sha256='9'*64)],
        installedApkPath='/data/app/synthetic/base.apk')
    proof_raw = raw(proof);report['targetByteProofSha256'] = digest(proof_raw)
    for row in report['iterations']:
        nonce = '%032x' % row['index'];prefix = 'iteration-%02d/' % row['index']
        armed = dict(name='collapse', target='collapsed', armedUptimeMs=800, expiresUptimeMs=15800)
        request = dict(x=100, startY=600, endY=200, targetPid='123', expiresUptimeMs=15800,
            targetByteProofSha256=digest(proof_raw), targetApkPath=proof['installedApkPath'], targetApkBytes=build['apkBytes'])
        trace = dict(n.PROTOCOLS['formal-collapse'], startUptimeMs=1000, expiresUptimeMs=15800,
                     cleanup=None, error='', events=[])
        for i in range(21):
            at = 1000+i*16
            trace['events'].append(dict(action=0 if i==0 else 1 if i==20 else 2,
                downTime=1000, plannedUptimeMs=at, eventTime=at, callStartUptimeMs=at,
                callEndUptimeMs=at+1, x=100, y=600-20*i, injected=True, accepted=True,
                cleanup=False, error='', sync=i==20))
        target = dict(sourceCommit=build['sourceCommit'], sourceTree=build['sourceTree'], dirtySource=False)
        focus = dict(displayId=0, packageName=n.TARGET,
            component=n.TARGET + '/local.pocketchat.ExperienceBenchmarkActivity',
            raw='  mCurrentFocus=Window{abcd u0 local.pocketchat.test/local.pocketchat.ExperienceBenchmarkActivity}\n  mTopFocusedDisplayId=0\n')
        actual = dict(schema=1, status='passed', purpose='formal-collapse', nonce=nonce, gesture='formal-collapse',
            sourceCommit=build['sourceCommit'], sourceTree=build['sourceTree'], packageName=n.SELF,
            targetPackage=n.TARGET, buildIdentity=copy.deepcopy(compiled), targetBuildIdentity=target,
            targetBuildIdentityAfter=copy.deepcopy(target), driverApkSha256=compiled['apkSha256'],
            targetApkSha256=build['apkSha256'], signerCertificateSha256=compiled['signerCertificateSha256'],
            targetApkHashSource='preflight-installed-byte-proof', targetByteProofSha256=digest(proof_raw),
            targetApkPathBefore=proof['installedApkPath'], targetApkPathAfter=proof['installedApkPath'],
            targetApkBytesBefore=build['apkBytes'], targetApkBytesAfter=build['apkBytes'],
            targetLastModifiedBefore=10, targetLastModifiedAfter=10, targetLastUpdateBefore=20, targetLastUpdateAfter=20,
            executionBackend='shell-input-manager-global-v1', executionUid=2000,
            inputTargetUid=10123, targetUidBefore=10123, targetUidAfter=10123,
            targetStartTicksBefore='200', targetStartTicksAfter='200', driverPid=456, driverStartTicks='300',
            displayId=0, focusBefore=copy.deepcopy(focus), focusAfter=copy.deepcopy(focus),
            tracePersistence='memory-until-terminal',
            targetPidBefore='123', targetPidAfter='123', createdUptimeMs=840, startedUptimeMs=850,
            connectStartUptimeMs=900, connectEndUptimeMs=940, readyUptimeMs=950,
            startupMs=100, finishedUptimeMs=1322, expiresUptimeMs=15800, trace=trace)
        name = 'native-input-'+nonce+'-formal-collapse.json'
        data = add_file(report, root, prefix+name, actual)
        for suffix in ('-stdout.log','-stderr.log'):
            add_file(report, root, prefix+name[:-5]+suffix, b'')
        add_file(report, root, prefix+'native-input-driver-build.json', compiled_raw)
        for filename,value in signing.items():add_file(report,root,prefix+filename,value)
        add_file(report, root, prefix+'native-input-target-proof-'+nonce+'.json', proof_raw)
        add_file(report, root, prefix+'native-input-setup-'+nonce+'.json', dict(
            sourceCommit=build['sourceCommit'], nonce=nonce, installationRequested=False,
            actualInstalledApkRead=True, apkSha256=compiled['apkSha256'], apkBytes=80,
            signerCertificateSha256=compiled['signerCertificateSha256']))
        row['nativeInputDriver'] = dict(purpose='formal-collapse', nonce=nonce, buildSha256=digest(compiled_raw),
            receipts=[dict(file=name, sha256=digest(data), gesture='formal-collapse', request=request,
                hostStartedMonotonicNs=1000000, hostCompletedMonotonicNs=2000000)])
        row['collapseInput'] = dict(armed=armed, **{'from':[100,600], 'to':[100,200]}, startupMs=100,
            readyUptimeMs=950, armedActionToReadyMs=150, hostInvocationMs=1.0)
        action = next(a for a in row['actions'] if a['name']=='collapse')
        action.update(inputUpUptimeMs=1320, inputDurationMs=320, drawUptimeMs=1340)
        transfers=[]
        for kind, result in [('armed',armed), ('measurement',action)]:
            envelope=dict(runNonce=nonce, sourceCommit=build['sourceCommit'],
                buildIdentity={'apkSha256':build['apkSha256']}, event=dict(kind=kind,result=result))
            data=raw(envelope)
            transfers.append(dict(rawUtf8=data.decode(),receipt=dict(runNonce=nonce,payloadBytes=len(data),payloadSha256=digest(data))))
        add_file(report,root,prefix+'experienceBenchmark-transport.json',transfers)
    return compiled
