"""Independent twelfth real-Android phase of the production TLS acceptance.

Uses the original IP fixture allocator/endpoint/routes, a fresh three-origin CA,
and fresh actual TLS13 peer sockets. Never called to replace any of eleven TLS
cases or the independent CPU/IP gates. No external network is implemented.
"""
import hashlib
import re
import shlex
import time
from pathlib import Path
from fingerprint_fixture_server import AndroidUserCa
from ip_timezone_fixture_server import IpFixtureCertificates,IpTimeZoneFleet
from tls_cpu_ip_combo_server import TlsCpuIpCapture
from tls_cpu_ip_combo_contract import CASE_FILE,validate_combo
from tls_acceptance_server import strict_json,require
from profile_invocation_contract import verify_installed
ROOT=Path(__file__).resolve().parents[2]
PACKAGE='local.pocketchat.test'
URI='content://'+PACKAGE+'.gecko-tls-cpu-ip-combo-evidence'
ACTIVITY=PACKAGE+'/local.pocketchat.GeckoTlsCpuIpComboIntegrationActivity'
class ComboFailure(ValueError):
    def __init__(self,envelope,error):
        self.envelope=envelope
        super().__init__('Product TLS fixture: independent combined production workload failed ('+type(error).__name__+')')


def scope_command(action,source,nonce):
    require(action in ('prepare','clear') and re.fullmatch('[0-9a-f]{40}',source) and re.fullmatch('[0-9a-f]{32}',nonce),'exact twelfth fixture scope command')
    return ['shell',shlex.join(['content','call','--uri',URI,'--method',action,'--extra','sourceCommit:s:'+source,'--extra','runNonce:s:'+nonce])]

def safe_trust(receipt):
    fields={'method','androidUser','adbRoot','selinuxEnforcing','installedPublicCaBytesMatch','ownerAndMode','selinuxContext','subjectHashOld','appForceStoppedAfterInstall','publicCaPemSha256','expectedLeafDerSha256','evidenceShellUid','shellRestoredAfterInstall','removedAfterExecution','cleanupRootUid','cleanupShellUid','shellRestoredAfterCleanup'}
    return {k:v for k,v in receipt.items() if k in fields}

def read_activity(raw,source,nonce,expected):
    require(len(raw)<=262144,'bounded combined original')
    text=raw.decode('utf-8','strict')
    if not text.strip() or text.startswith(('Error while accessing provider:','Error:','No result found.')):return None
    value=strict_json(raw)
    require(type(value) is dict and type(value.get('schema')) is int and value['schema']==1 and value.get('fixtureType')=='gecko-production-tls-cpu-ip-combo-v1' and type(value.get('runNonce')) is str and re.fullmatch('[0-9a-f]{32}',value['runNonce']),'typed combined original invocation')
    if value['runNonce']!=nonce:return None
    require(value.get('sourceCommit')==source and value.get('sourceTree')==expected['sourceTree'],'same combined installed source/tree')
    verify_installed(value.get('buildIdentity',{}),expected);return value

def run_combo(adb,output,source,tree,identity,nonce):
    require(re.fullmatch('[0-9a-f]{40}',source) and re.fullmatch('[0-9a-f]{40}',tree) and re.fullmatch('[0-9a-f]{32}',nonce),'exact independent phase tuple')
    path=Path(output)/CASE_FILE;require(not path.exists() and not path.is_symlink(),'fresh original twelfth case')
    sdk=identity['sdkBuildIdentity'];binding=dict(sourceCommit=source,sourceTree=tree,runNonce=nonce,integrationApkSha256=identity['apkSha256'],sdkRunId=sdk['runId'],sdkRunAttempt=sdk['runAttempt'])
    certificates=server=capture=ca=None;scope=False;mappings=[];host_tls={};setup={};process={};system={};device=None;original=None;error=None;wire={};routes={}
    cleanup=dict(appStopped=False,scopeCleared=False,reverseRemoved=False,caRemoved=False,privateMaterialRemoved=False,serverQuiesced=False,appDataCleared=False,shellUidRestored=False)
    def cold_stop():
        adb('shell','am','force-stop',PACKAGE)
        for slot in range(1,8):require(not adb('shell','pidof',PACKAGE+':profile'+str(slot),check=False).stdout.strip(),'old environment process alive before combined setup')
    try:
        require(adb('shell','id','-u').stdout.strip()==b'2000' and adb('shell','getconf','_NPROCESSORS_ONLN').stdout.strip()==b'4','same controlled shell/four CPU guest')
        cold_stop();require(adb('shell','pm','clear',PACKAGE).stdout.strip()==b'Success','fresh independent combined integration data')
        system['before']=adb('shell','getprop','persist.sys.timezone').stdout.decode('ascii').strip()
        certificates=IpFixtureCertificates();capture=TlsCpuIpCapture(certificates,binding)
        server=IpTimeZoneFleet(certificates,(ROOT/'tests/gecko/assets/worker-policy-page.js').read_text(),(ROOT/'tests/gecko/assets/tls-cpu-ip-combo-page.js').read_text(),binding).start()
        server.control(dict(sourceCommit=source,runNonce=nonce,action='stage',case='default-socks'))
        ca=AndroidUserCa(adb,certificates);ca.install();host_tls=dict(certificates.public,binding=binding)
        existing=adb('reverse','--list').stdout.decode('ascii').splitlines()
        for guest,host in server.ports().items():
            require(not any('tcp:'+str(guest) in row.split() for row in existing),'cannot replace an existing combined guest mapping')
            adb('reverse','tcp:'+str(guest),'tcp:'+str(host));mappings.append(guest)
        # This setup provider is in the existing early-return process. Neither
        # the default process nor a generic manual seed runs before prepareIp.
        scope=True;require(b'status=armed' in adb(*scope_command('prepare',source,nonce)).stdout,'actual original prepareIp scope')
        setup=strict_json(adb('exec-out','content','read','--uri',URI+'/setup').stdout)
        require(setup.get('sourceCommit')==source and setup.get('sourceTree')==tree and setup.get('runNonce')==nonce and setup.get('integrationApkSha256')==identity['apkSha256'] and setup.get('slot')==6 and setup.get('timezoneSealedRecordMissing') is True and setup.get('actualDefaultStoreLoadYet') is False and setup.get('manualSeedAppliedToIpScope') is False,'actual missing timezone before first profile use')
        command=['am','start','-W','-n',ACTIVITY,'--es','sourceCommit',source,'--es','runNonce',nonce,'--es','expectedLeafSha256',certificates.leaf_sha]
        deadline=time.monotonic()+180;adb('shell',shlex.join(command))
        while time.monotonic()<deadline:
            remaining=deadline-time.monotonic()
            if remaining<=0:break
            raw=adb('exec-out','content','read','--uri',URI+'/report',check=False,timeout=min(20,remaining)).stdout
            value=read_activity(raw,source,nonce,identity)
            if value is not None:
                device=value;original=raw
                if value.get('status') in ('passed','failed'):break
            time.sleep(.25)
        require(device is not None and device.get('status')=='passed','actual combined production workload failed or timed out')
        pid=device.get('process',{}).get('pid');observed=adb('shell','pidof',PACKAGE+':profile6').stdout.decode('ascii').strip()
        require(type(pid) is int and pid>0 and observed==str(pid) and adb('shell','id','-u').stdout.strip()==b'2000','independent combined actual PID ownership')
        process=dict(schema=1,sourceCommit=source,sourceTree=tree,runNonce=nonce,slot=6,processName=PACKAGE+':profile6',expectedPid=pid,observedPid=observed,shellUid=2000)
        system['after']=adb('shell','getprop','persist.sys.timezone').stdout.decode('ascii').strip();require(system['before']==system['after'],'Android system timezone changed')
    except Exception as failure:error=failure
    finally:
        # Freeze every host writer only after app stop and server joins. Each
        # cleanup still runs if another fails; a failure cannot qualify a case.
        def clear_scope():require(b'status=cleared' in adb(*scope_command('clear',source,nonce)).stdout,'owned combined scope cleanup')
        def remove_reverse():
            for guest in mappings:adb('reverse','--remove','tcp:'+str(guest))
        def remove_private():certificates.close();require(not certificates.directory.exists(),'combined private material remains');host_tls['privateMaterialRemoved']=True
        def clear_data():require(adb('shell','pm','clear',PACKAGE).stdout.strip()==b'Success','combined integration data cleanup')
        def restored():require(adb('shell','id','-u').stdout.strip()==b'2000','shell UID restored')
        actions=[('appStopped',cold_stop)]
        if scope:actions.append(('scopeCleared',clear_scope))
        if server is not None:actions.append(('serverQuiesced',server.close))
        actions.append(('reverseRemoved',remove_reverse))
        if ca is not None:actions.append(('caRemoved',ca.remove))
        if certificates is not None:actions.append(('privateMaterialRemoved',remove_private))
        actions.extend([('appDataCleared',clear_data),('shellUidRestored',restored)])
        for key,action in actions:
            try:action();cleanup[key]=True
            except Exception as failure:error=error or failure
        if ca is not None:host_tls['trustInstallation']=safe_trust(ca.receipt)
        if server is not None:
            try:routes=server.snapshot();wire=capture.snapshot(server)
            except Exception as failure:error=error or failure
        if original is not None:
            require(0<len(original)<=262144,'bounded original combined device bytes')
            with path.open('xb') as out:out.write(original)
    envelope=dict(schema=1,label='combined-cpu-ip-tls13',status='passed' if error is None and all(cleanup.values()) else 'failed',report=CASE_FILE,reportSha256=hashlib.sha256(original).hexdigest() if original is not None else None,prelaunchSetup=setup,processSample=process,routeReceipts=routes,hostTls=host_tls,systemTimeZone=system,cleanup=cleanup,wire=wire)
    if error is not None:raise ComboFailure(envelope,error) from error
    engine=re.findall(r'^\s*static final String VERSION=("(?:[^"\\]|\\.)*");',(ROOT/'app/src/main/java/local/pocketchat/GeckoWebView.java').read_text(),re.M);require(len(engine)==1,'exact actual Gecko version')
    import json
    try:finding=validate_combo(device,envelope,source=source,expected=identity,run=nonce,engine=json.loads(engine[0]))
    except Exception as failure:raise ComboFailure(envelope,failure) from failure
    return envelope,finding
