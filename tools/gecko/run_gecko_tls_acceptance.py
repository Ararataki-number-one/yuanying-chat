#!/usr/bin/env python3
"""Real production Gecko-web TLS cold profile/UI/persistent-SW/concurrent acceptance."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from profile_invocation_contract import expected_build,verify_installed
from tls_acceptance_server import TlsAcceptanceServer,CASE_SPECS,GUEST_PORT,strict_json,require
from tls_acceptance_contract import validate_device,validate_wire,validate_cross
from tls_fixture_scope_contract import validate_manual_scope,validate_manual_cross
from run_gecko_tls_cpu_ip_combo import run_combo,ComboFailure
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/browser'))
from fingerprint_fixture_server import EphemeralCertificates,AndroidUserCa
PACKAGE='local.pocketchat.test'
URI='content://'+PACKAGE+'.tls-acceptance'
def manual_scope_command(action,source,run,slot):
    require(action in ('prepare','clear','inspect') and re.fullmatch('[0-9a-f]{40}',source) and re.fullmatch('[0-9a-f]{32}',run) and type(slot) is int and slot in (1,2),'exact explicit manual TLS fixture command')
    purpose='local.pocketchat.GeckoTlsAcceptanceActivity$Profile'+str(slot)
    return ['shell',shlex.join(['content','call','--uri',URI,'--method',action,'--extra','sourceCommit:s:'+source,'--extra','runNonce:s:'+run,'--extra','slot:i:'+str(slot),'--extra','purpose:s:'+purpose])]


def manual_claim(raw):
    require(type(raw) is bytes and 0<len(raw)<=8192 and b'status=armed' in raw,'bounded armed manual scope response')
    values=re.findall(rb'claimNonce=([0-9a-f]{32})(?=[,}\]])',raw)
    require(len(values)==1,'exact explicit manual scope claim');return values[0].decode('ascii')

def scope_processes():
    return [PACKAGE]+[PACKAGE+':profile'+str(slot) for slot in range(1,8)]

def observe_fixture_process(parts,result,observations,phase,label,command_error=''):
    """Preserve raw command outcome without mistaking a failed query for absence."""
    require(type(parts) is tuple and len(parts)==3 and parts[:2]==('shell','pidof') and parts[2] in scope_processes(),'fixed fixture process observation')
    require(type(observations) is list and len(observations)<4096 and phase in ('initial','cold-stop','manual-prepare','collect','resident','cleanup','combined') and (label=='' or label in {s[0] for s in CASE_SPECS}),'bounded fixture process observation owner')
    require(command_error in ('','TimeoutExpired','OSError'),'fixed process command exception type')
    stdout=result.stdout;stderr=result.stderr;code=result.returncode
    typed=type(stdout) is bytes and type(stderr) is bytes and type(code) is int
    bounded=typed and len(stdout)<=512 and len(stderr)<=4096
    pids=[]
    if bounded and re.fullmatch(rb'[1-9][0-9]{0,9}(?:[ \t]+[1-9][0-9]{0,9})*[\r\n]*',stdout):pids=[int(value) for value in stdout.split()]
    valid=not command_error and bounded and not stderr and ((code==0 and 0<len(pids)<=16 and len(set(pids))==len(pids)) or (code==1 and not stdout.strip()))
    row=dict(sequence=len(observations)+1,phase=phase,label=label,processName=parts[2],commandErrorType=command_error or None,returnCode=code if type(code) is int else None,pids=pids if valid else [],status=('present' if pids else 'absent') if valid else 'invalid-command-result',stdoutBytes=len(stdout) if type(stdout) is bytes else None,stderrBytes=len(stderr) if type(stderr) is bytes else None,stdoutSha256=hashlib.sha256(stdout).hexdigest() if type(stdout) is bytes else None,stderrSha256=hashlib.sha256(stderr).hexdigest() if type(stderr) is bytes else None)
    observations.append(row)
    require(valid,'fixed process observation failed for '+parts[2])
    return row


PROC_START_HOSTING=frozenset(('service','content provider','activity','broadcast','restart','added application','backup','on-hold','top-activity','next-activity','next-top-activity','link fail','webview_service'))

def declared_fixture_components(manifests):
    result=set();android='{http://schemas.android.com/apk/res/android}'
    for raw in manifests:
        require(type(raw) is bytes and 0<len(raw)<=131072,'bounded source manifest')
        root=ET.fromstring(raw)
        for node in root.iter():
            if node.tag not in ('activity','activity-alias','provider','receiver','service'):continue
            name=node.get(android+'name')
            require(type(name) is str and re.fullmatch(r'local\.pocketchat\.[A-Za-z0-9_.$]+',name),'fixed declared application component')
            result.add(PACKAGE+'/'+name)
    return frozenset(result)

def process_start_events(raw,pid,components):
    """Extract only a typed exact-process event; never return another log line."""
    require(type(pid) is int and 0<pid<2147483648 and type(components) is frozenset,'fixed live process event owner')
    unknown=dict(status='unknown',reason='no-exact-process-event',eventCount=0)
    if type(raw) is not bytes or len(raw)>131072:return dict(unknown,reason='event-output-bound')
    lines=raw.splitlines()
    if len(lines)>258 or any(len(line)>2048 for line in lines):return dict(unknown,reason='event-line-bound')
    matched=[]
    for line in lines:
        text=line.decode('ascii','replace').strip()
        match=re.fullmatch(r'\[([0-9]+),\s*([0-9]+),\s*([0-9]+),\s*([^,]+),\s*([^,]+),\s*(.*)\]',text)
        if match is None:continue
        user,actual,uid=int(match[1]),int(match[2]),int(match[3]);process=match[4].strip()
        if actual!=pid or process!=PACKAGE:continue
        hosting=match[5].strip();component=match[6].strip()
        if component.startswith('ComponentInfo{') and component.endswith('}'):component=component[14:-1]
        elif component.startswith('{') and component.endswith('}'):component=component[1:-1]
        matched.append((user,uid,hosting,component))
    if len(matched)!=1:return dict(unknown,reason='ambiguous-process-events' if matched else 'no-exact-process-event',eventCount=len(matched))
    user,uid,hosting,component=matched[0]
    if user>2147483647 or uid>2147483647:return dict(unknown,reason='event-identity-bound',eventCount=1)
    if hosting not in PROC_START_HOSTING:return dict(unknown,reason='unknown-hosting-type',eventCount=1)
    if component not in components:return dict(unknown,reason='unknown-component',eventCount=1)
    return dict(status='observed',reason='exact-process-start-event',eventCount=1,user=user,pid=pid,uid=uid,processName=PACKAGE,hostingType=hosting,component=component)

def failed_manual_main_start(adb,error,observations,components):
    # This is diagnosis after an existing failure, never a readiness decision.
    if not isinstance(error,ValueError) or str(error)!='Product TLS fixture: all generic fixture writers must be absent before manual preparation' or not observations:return None
    last=observations[-1]
    if last.get('phase')!='manual-prepare' or last.get('processName')!=PACKAGE or last.get('status')!='present' or last.get('returnCode')!=0 or type(last.get('pids')) is not list or len(last['pids'])!=1:return None
    pid=last['pids'][0]
    if type(pid) is not int or not 0<pid<2147483648 or last.get('label') not in {s[0] for s in CASE_SPECS}:return None
    base=dict(schema=1,kind='failed-tls-fixture-main-start',diagnosticOnly=True,readOnly=True,originalFailurePreserved=True,phase=last['phase'],label=last['label'],observedPid=pid,queryAttempted=True)
    try:
        result=adb('shell','logcat','-b','events','-d','-t','256','-v','raw','-s','am_proc_start:I',check=False,timeout=5)
        if type(result.returncode) is not int or result.returncode!=0 or type(result.stderr) is not bytes or result.stderr:return dict(base,status='unknown',reason='event-command-failed')
        return dict(base,**process_start_events(result.stdout,pid,components))
    except subprocess.TimeoutExpired:return dict(base,status='unknown',reason='event-command-timeout')
    except Exception:return dict(base,status='unknown',reason='event-observation-unavailable')


def prepare_manual_scope(adb,source,run,spec,before_label,prearmed=None):
    label,slot=spec[:2]
    require(not spec[6] and adb('shell','id','-u').stdout.strip()==b'2000','cold manual scope shell owner')
    require(not adb('shell','pidof',PACKAGE+':profile'+str(slot),check=False).stdout.strip(),'actual target process must be absent before scope/admission')
    if prearmed is not None:
        require(label=='concurrent-default-tls12' and before_label=='concurrent-strict-tls13' and prearmed.get('label')==label and prearmed.get('preparationBeforeLabel')==before_label and prearmed.get('sourceCommit')==source and prearmed.get('runNonce')==run,'exact early concurrent scope reuse')
        claim=manual_claim(adb(*manual_scope_command('inspect',source,run,slot)).stdout)
        require(claim==prearmed.get('claimNonce'),'concurrent scope claim must remain exact')
        return dict(prearmed,scopeReusedBeforeStart=True,scopeInspectionVerified=True,reuseAtLabel=label)
    # A target-process check alone cannot exclude another environment's
    # integration Application enumerating this slot. Prepare only while all
    # ordinary fixture processes are absent; setup itself never seeds generic.
    for process in scope_processes():require(not adb('shell','pidof',process,check=False).stdout.strip(),'all generic fixture writers must be absent before manual preparation')
    require(b'status=cleared' in adb(*manual_scope_command('clear',source,run,slot)).stdout,'explicit owned manual scope clear')
    claim=manual_claim(adb(*manual_scope_command('prepare',source,run,slot)).stdout)
    return dict(label=label,slot=slot,sourceCommit=source,runNonce=run,shellUid=2000,processAbsent=True,ownedClearObserved=True,prepared=True,claimNonce=claim,preparationBeforeLabel=before_label,allListedFixtureProcessesAbsentAtPreparation=True,scopeProcessesChecked=scope_processes(),scopeReusedBeforeStart=False,scopeInspectionVerified=False,reuseAtLabel='')

def run_original_cases(cold_stop,prepare_scope,collect,resident):
    prearmed=None
    for spec in CASE_SPECS:
        label=spec[0]
        if not spec[6] and label!='concurrent-default-tls12':cold_stop()
        if label=='concurrent-strict-tls13':
            next_spec=CASE_SPECS[9]
            require(next_spec[0]=='concurrent-default-tls12' and next_spec[1]==2,'original concurrent case ordering')
            prearmed=prepare_scope(next_spec,label,None)
        if label=='concurrent-default-tls12':
            require(prearmed is not None,'slot2 must be prepared before any concurrent runtime starts')
            scoped=prepare_scope(spec,'concurrent-strict-tls13',prearmed)
        else:scoped=None if spec[6] else prepare_scope(spec,label,None)
        collect(spec,scoped)
        if label=='concurrent-default-tls12':resident('both-resident')
        if label=='concurrent-strict-resample-tls12':resident('after-resample')


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(65536),b''):digest.update(block)
    return digest.hexdigest()

def snapshot():
    paths=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    return {name:sha(ROOT/name) for name in paths if name and (ROOT/name).is_file()}

def finish_resources(adb,cold_stop,server,certificates,ca,reversed_port,cleanup,errors,host_tls):
    try:
        cold_stop();cleanup['appStopped']=True
        require(adb('shell','pm','clear',PACKAGE).stdout.strip()==b'Success','integration data/proxy cleanup');cleanup['appDataCleared']=True
    except Exception as error:errors.append(dict(stage='app-cleanup',errorType=type(error).__name__))
    if reversed_port:
        try:adb('reverse','--remove','tcp:'+str(GUEST_PORT));cleanup['reverseRemoved']=True;host_tls['reverseRemoved']=True
        except Exception as error:errors.append(dict(stage='reverse-cleanup',errorType=type(error).__name__))
    if server is not None:
        try:server.close();cleanup['serverClosed']=server.closed;cleanup['serverThreadsJoined']=server.joined
        except Exception as error:errors.append(dict(stage='server-cleanup',errorType=type(error).__name__))
    if ca is not None:
        try:ca.remove();cleanup['caRemoved']=True
        except Exception as error:errors.append(dict(stage='public-ca-cleanup',errorType=type(error).__name__))
    if certificates is not None:
        try:certificates.close();cleanup['privateMaterialRemoved']=not certificates.directory.exists();host_tls['privateMaterialRemoved']=cleanup['privateMaterialRemoved']
        except Exception as error:errors.append(dict(stage='private-material-cleanup',errorType=type(error).__name__))
    try:cleanup['shellUidRestored']=adb('shell','id','-u').stdout.strip()==b'2000'
    except Exception as error:errors.append(dict(stage='shell-cleanup',errorType=type(error).__name__))
    return server.snapshot() if server else None

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--adb',default='adb');p.add_argument('--serial',default='emulator-5554');p.add_argument('--apk',required=True,type=Path);p.add_argument('--source',required=True);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip()
    require(a.serial=='emulator-5554' and a.source==source and re.fullmatch('[0-9a-f]{40}',source),'exact controlled source/emulator')
    require(not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip(),'clean immutable selected source')
    output=a.output.absolute();require(not output.exists() and all(not q.is_symlink() for q in (output,*output.parents)),'fresh ordinary output')
    gradle=(ROOT/'app/build.gradle').read_text();identity=expected_build(a.apk,source,tree,re.search(r"versionName '([^']+)'",gradle)[1],int(re.search(r'versionCode ([0-9]+)',gradle)[1]))
    before=snapshot();output.mkdir(parents=True);run=uuid.uuid4().hex
    server=certificates=ca=None;reversed_port=False;entries=[];process_checks=[];errors=[];host_tls={};guest={};checked=None;manual_checks=[];combined=None;combined_finding=None;fixture_process_observations=[];observation_context=['initial',''];failed_main_start=None
    cleanup=dict(appStopped=False,appDataCleared=False,reverseRemoved=False,serverClosed=False,serverThreadsJoined=False,caRemoved=False,privateMaterialRemoved=False,shellUidRestored=False)
    def adb(*parts,check=True,timeout=25):
        fixed_pidof=len(parts)==3 and parts[:2]==('shell','pidof') and parts[2] in scope_processes()
        try:result=subprocess.run([a.adb,'-s',a.serial,*parts],capture_output=True,check=False if fixed_pidof else check,timeout=timeout)
        except (subprocess.TimeoutExpired,OSError) as error:
            if fixed_pidof:
                outcome=subprocess.CompletedProcess(parts,None,getattr(error,'stdout',None) or b'',getattr(error,'stderr',None) or b'')
                try:observe_fixture_process(parts,outcome,fixture_process_observations,*observation_context,command_error='TimeoutExpired' if isinstance(error,subprocess.TimeoutExpired) else 'OSError')
                except ValueError:pass
            raise
        if fixed_pidof:
            observe_fixture_process(parts,result,fixture_process_observations,*observation_context)
            if check:result.check_returncode()
        return result
    def prepare_scope(spec,before_label,prearmed):
        observation_context[:]=['manual-prepare',spec[0]]
        return prepare_manual_scope(adb,source,run,spec,before_label,prearmed)
    def cold_stop():
        adb('shell','am','force-stop',PACKAGE)
        for process in scope_processes():require(not adb('shell','pidof',process,check=False).stdout.strip(),'old environment remains alive')
    def collect(spec,scoped):
        label,slot,mode,rfp,retain,stale,resample,version,success,service=spec
        observation_context[:]=['collect',label]
        if scoped is not None:manual_checks.append(scoped)
        case=uuid.uuid4().hex;binding=server.begin(label,case)
        entry=dict(label=label,binding=binding,status='failed');entries.append(entry)
        command=['am','start','-W','-n',PACKAGE+'/local.pocketchat.GeckoTlsAcceptanceActivity$Profile'+str(slot),'--es','runNonce',run,'--es','caseNonce',case,'--es','sourceCommit',source,'--es','tlsMode',mode,'--es','expectedLeafSha256',certificates.leaf_sha,'--ei','peerPort',str(binding['port'])]
        for key,value in dict(rfp=rfp,retain=retain,staleUser=stale,resample=resample,expectSuccess=success,service=service,saveDefault=label=='pending-default-tls12').items():command+=['--ez',key,str(value).lower()]
        adb('shell',shlex.join(command));deadline=time.monotonic()+150;device=None
        while time.monotonic()<deadline:
            raw=adb('exec-out','content','read','--uri','content://'+PACKAGE+'.tls-acceptance/report/'+case+'/'+str(slot),check=False).stdout
            try:value=strict_json(raw)
            except (ValueError,UnicodeError):time.sleep(.25);continue
            require(value.get('runNonce')==run and value.get('caseNonce')==case and value.get('sourceCommit')==source,'stale or foreign original packet')
            if value.get('status') in ('passed','failed'):
                path=output/('case-'+label+'.json');path.write_bytes(raw);entry.update(report=path.name,reportSha256=hashlib.sha256(raw).hexdigest());device=value;break
            time.sleep(.25)
        require(device is not None,'workload did not terminate; timeout is not protocol rejection')
        entry['device']=device
        finding=validate_device(device,spec=spec,binding=binding,run=run,source=source,tree=tree,identity=identity,leaf=certificates.leaf_sha)
        validate_manual_scope(device,spec=spec,binding=binding,run=run,source=source,tree=tree,identity=identity)
        require(adb('shell','pidof',PACKAGE+':profile'+str(slot)).stdout.decode('ascii').strip()==str(finding['pid']),'actual native report PID owner')
        entry.update(status='passed',finding=finding)
    def resident(stage):
        observation_context[:]=['resident','']
        require(adb('shell','id','-u').stdout.strip()==b'2000','actual shell UID2000')
        selected={e['label']:e for e in entries}
        for label in ('concurrent-strict-tls13','concurrent-default-tls12'):
            finding=selected[label]['finding'];observed=adb('shell','pidof',PACKAGE+':profile'+str(finding['slot'])).stdout.decode('ascii').strip()
            row=dict(stage=stage,slot=finding['slot'],expectedPid=finding['pid'],observedPid=observed,shellUid=2000);process_checks.append(row);require(observed==str(finding['pid']),'both different environment runtimes must remain resident')
    try:
        emulator=adb('shell','getprop','ro.kernel.qemu').stdout.strip();sdk=adb('shell','getprop','ro.build.version.sdk').stdout.strip();cpus=adb('shell','getconf','_NPROCESSORS_ONLN').stdout.strip();uid=adb('shell','id','-u').stdout.strip()
        require(emulator==b'1' and sdk==b'35' and cpus==b'4' and uid==b'2000','actual API35/four CPUs/shell2000; no fallback')
        guest=dict(actualEmulator=True,api=35,onlineCpus=4,evidenceShellUid=2000)
        verify_installed(strict_json(adb('exec-out','content','read','--uri','content://'+PACKAGE+'.evidence/build-identity').stdout),identity)
        require(not any('tcp:'+str(GUEST_PORT) in line.split() for line in adb('reverse','--list').stdout.decode('ascii').splitlines()),'existing guest mapping cannot be replaced')
        certificates=EphemeralCertificates();ca=AndroidUserCa(adb,certificates);ca.install()
        host_tls=dict(certificates.public,trustInstallation=ca.receipt,guestPort=GUEST_PORT,binding=dict(sourceCommit=source,sourceTree=tree,runNonce=run,integrationApkSha256=identity['apkSha256'],sdkRunId=identity['sdkBuildIdentity']['runId'],sdkRunAttempt=identity['sdkBuildIdentity']['runAttempt']))
        server=TlsAcceptanceServer(certificates,run,source,(ROOT/'tests/gecko/assets/tls-acceptance-page.js').read_text(),(ROOT/'tests/gecko/assets/tls-acceptance-worker.js').read_text()).start()
        adb('reverse','tcp:'+str(GUEST_PORT),'tcp:'+str(server.port));reversed_port=True
        require(adb('shell','pm','clear',PACKAGE).stdout.strip()==b'Success','fresh integration-only initial data')
        def observed_cold_stop():
            observation_context[:]=['cold-stop','']
            cold_stop()
        run_original_cases(observed_cold_stop,prepare_scope,collect,resident)
        validate_cross(entries,process_checks)
        validate_manual_cross(entries,manual_checks,run=run,source=source)
    except Exception as error:
        errors.append(dict(stage='actual-production-native-and-wire',errorType=type(error).__name__,reason=str(error)[:400] if isinstance(error,ValueError) and str(error).startswith(('Gecko product TLS evidence:','Product TLS fixture:')) else 'actual-production-workload-failed'))
        try:failed_main_start=failed_manual_main_start(adb,error,fixture_process_observations,declared_fixture_components([(ROOT/'app/src/main/AndroidManifest.xml').read_bytes(),(ROOT/'tests/gecko/AndroidManifest.xml').read_bytes()]))
        except Exception:failed_main_start=dict(schema=1,status='unknown',reason='source-component-observation-unavailable',diagnosticOnly=True,originalFailurePreserved=True)
    finally:
        observation_context[:]=['cleanup','']
        host=finish_resources(adb,cold_stop,server,certificates,ca,reversed_port,cleanup,errors,host_tls)
    if len(entries)==len(CASE_SPECS) and all(e['status']=='passed' for e in entries) and host is not None:
        try:checked=validate_wire(host,entries,run=run,source=source)
        except Exception as error:errors.append(dict(stage='final-original-wire-replay',errorType=type(error).__name__,reason=str(error)[:400]))
    if checked is not None and not errors and all(cleanup.values()):
        try:
            observation_context[:]=['combined','']
            combined,combined_finding=run_combo(adb,output,source,tree,identity,run)
        except Exception as error:
            if isinstance(error,ComboFailure):combined=error.envelope
            errors.append(dict(stage='independent-cold-cpu-ip-tls13',errorType=type(error).__name__,reason=str(error)[:400] if isinstance(error,ValueError) else 'combined-workload-failed'))
    stable=snapshot()==before;passed=checked is not None and combined_finding is not None and not errors and all(cleanup.values()) and stable
    public_entries=[{k:v for k,v in e.items() if k!='device'} for e in entries]
    result=dict(schema=1,kind='gecko-production-tls-v1',status='passed' if passed else 'failed',diagnosticOnly=True,releaseAcceptance=False,sourceCommit=source,sourceTree=tree,runId=os.environ.get('GITHUB_RUN_ID'),runAttempt=os.environ.get('GITHUB_RUN_ATTEMPT'),runNonce=run,expectedBuildIdentity=identity,guest=guest,caseRecords=public_entries,processChecks=process_checks,manualScopeChecks=manual_checks,fixtureProcessObservations=fixture_process_observations,fixtureMainStartDiagnostic=failed_main_start,combinedCase=combined,combinedFinding=combined_finding,coldCpuIpTlsCombinationMeasured=passed,hostTls=host_tls,host=host,cleanup=cleanup,errors=errors,checked=checked,sourceFiles=before,executionInputsUnchanged=stable,actualAndroidExecution=any(e['status']=='passed' for e in entries),actualGeckoExecution=any(e['status']=='passed' for e in entries),productionGeckoWebTlsWorkloadPassed=passed,persistentServiceWorkerTlsMeasured=passed,workerCoverageVerified=False,serviceWorkerCoverageVerified=False,fullTlsFingerprintEmulation=False,quicWireVerified=False,rawFatalAlertPacketDecoded=False,appIndependentTlsStacksCovered=False,scope='Actual production Gecko web connections under per-environment cold native TLS policy, exact native DEFAULT/effective readback, trusted controlled TLS12/TLS13 peers and original ClientHello bytes. Real desired-only UI pending state, nonempty old USER reconciliation, retained registration with separately measured Service Worker fetch across true cold start, and simultaneous isolated environments. Independent app downloader/connection checks/proxy entrance Java or other TLS stacks, arbitrary TLS fingerprints and QUIC are not covered.')
    raw=(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode();require(len(raw)<=4*1024*1024,'bounded final original summary');(output/'results.json').write_bytes(raw)
    print(json.dumps({k:result[k] for k in ('status','sourceCommit','productionGeckoWebTlsWorkloadPassed','executionInputsUnchanged')}));return 0 if passed else 1

if __name__=='__main__':raise SystemExit(main())
