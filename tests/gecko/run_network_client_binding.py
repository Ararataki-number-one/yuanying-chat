#!/usr/bin/env python3
"""One controlled framework null-binding/missing-component invocation, no retries."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/gecko'))
from integration_event_contract import EventTransfer,parse_receipt_line
from profile_invocation_contract import expected_build,verify_installed
from network_client_binding_contract import ACTION,PACKAGE,verify_runner_report
from diagnostic_capture_privacy import checked_bytes, safe_error_text


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb',required=True);parser.add_argument('--serial',default='emulator-5554')
    parser.add_argument('--apk',type=Path,default=ROOT/'app/build/outputs/apk/integration/app-x86_64-integration.apk')
    args=parser.parse_args();out=ROOT/'work/gecko-integration';out.mkdir(parents=True,exist_ok=True)
    target=out/'network-client-binding-results.json'
    if target.exists():raise ValueError('Existing binding invocation evidence must be archived before another run')
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip()
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():raise ValueError('Exact clean committed fixture source required')
    nonce=uuid.uuid4().hex;records=[];wrapper=dict(schema=1,status='failed',sourceCommit=source,runNonce=nonce,
        actualAndroidFixtureAttempted=False,fixtureInvocationCount=0,automaticRetryPerformed=False,adbObservations=records)
    def adb(*parts,binary=False,check=True,timeout=30):
        command=[args.adb,'-s',args.serial,*parts];index=len(records)+1
        try:run=subprocess.run(command,capture_output=True,timeout=timeout)
        except subprocess.TimeoutExpired as error:
            stdout,stderr=error.stdout or b'',error.stderr or b'';code=None
        else:stdout,stderr,code=run.stdout,run.stderr,run.returncode
        observation=dict(index=index,command=command,returnCode=code,streams={});public_stdout=stdout
        for label,raw in (('stdout',stdout),('stderr',stderr)):
            # Only logcat diagnostics are byte derivatives; primary commands remain exact.
            stored,privacy=checked_bytes(raw) if parts and parts[0]=='logcat' else (raw,None)
            path=out/('network-client-binding-adb-%04d-%s.raw.log'%(index,label));path.write_bytes(stored)
            observation['streams'][label]=dict(path=path.name,bytes=len(stored),sha256=hashlib.sha256(stored).hexdigest())
            if privacy is not None:
                observation['streams'][label]['capturePrivacy']=privacy
                if label=='stdout':public_stdout=stored
        records.append(observation)
        if check and code!=0:raise RuntimeError('Binding fixture ADB command failed: '+repr(observation))
        return public_stdout if binary else public_stdout.decode('utf-8',errors='strict')
    def raw_proof(raw):return dict(rawUtf8=raw.decode('utf-8',errors='strict'),utf8Bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    try:
        gradle=(ROOT/'app/build.gradle').read_text()
        expected=expected_build(args.apk.resolve(),source,tree,re.search(r"versionName '([^']+)'",gradle).group(1),int(re.search(r'versionCode (\d+)',gradle).group(1)))
        wrapper['buildIdentity']=expected
        # Only the fixed integration package is stopped/cleared; no production package option exists.
        adb('shell','am','force-stop',PACKAGE);adb('shell','pm','clear',PACKAGE);adb('logcat','-c')
        before=adb('exec-out','content','read','--uri','content://'+PACKAGE+'.evidence/build-identity',binary=True)
        wrapper['installedBefore']=raw_proof(before);verify_installed(json.loads(before),expected)
        wrapper['packageUidBeforeRaw']=adb('shell','cmd','package','list','packages','-U',PACKAGE)
        values=re.findall(r'^package:'+re.escape(PACKAGE)+r' uid:(\d+)\s*$',wrapper['packageUidBeforeRaw'],re.M)
        if len(values)!=1:raise ValueError('Installed test package UID unavailable')
        wrapper['packageUid']=int(values[0]);wrapper['androidSdk']=int(adb('shell','getprop','ro.build.version.sdk').strip())
        def fetch(uri):
            data=adb('exec-out','content','read','--uri',uri,binary=True)
            (out/'network-client-binding-native-event.raw.json').write_bytes(data);return data
        transfer=EventTransfer(identity=expected,nonce=nonce,slot=0,action=ACTION,command=1,fetch=fetch)
        wrapper['eventTransport']=transfer.records
        wrapper['actualAndroidFixtureAttempted']=True;wrapper['fixtureInvocationCount']=1
        wrapper['activityStartOutput']=adb('shell','am','start','-W','-n',PACKAGE+'/local.pocketchat.NetworkClientBindingIntegrationActivity',
            '--es','sourceCommit',source,'--es','eventNonce',nonce)
        deadline=time.monotonic()+90;received=False
        while time.monotonic()<deadline:
            log=adb('logcat','-d','-s','PocketGeckoIntegration:I','PocketClientBinding:E','AndroidRuntime:E','*:S')
            if 'FATAL EXCEPTION' in log:raise ValueError('Actual binding fixture process crashed: '+log)
            for line in log.splitlines():
                if 'PocketGeckoIntegration' not in line:continue
                receipt=parse_receipt_line(line)
                if receipt is None or receipt.get('runNonce')!=nonce:continue
                if receipt.get('kind')=='eventTransportError':raise ValueError('Original binding event publication failed: '+repr(receipt))
                event=transfer.read(receipt)
                if event.get('kind')!=ACTION:raise ValueError('Unexpected actual binding fixture event')
                wrapper['result']=event['result'];received=True;break
            if received:break
            time.sleep(.1)
        if not received:raise TimeoutError('No owned actual framework binding result within90 seconds')
        after=adb('exec-out','content','read','--uri','content://'+PACKAGE+'.evidence/build-identity',binary=True)
        wrapper['installedAfter']=raw_proof(after);verify_installed(json.loads(after),expected)
        wrapper['packageUidAfterRaw']=adb('shell','cmd','package','list','packages','-U',PACKAGE)
        wrapper['status']='passed';wrapper['verification']=verify_runner_report(wrapper,source)
    except BaseException as error:
        wrapper['status']='failed';wrapper['error']=type(error).__name__+': '+safe_error_text(error, use_repr=False)
        try:adb('logcat','-d',binary=True,check=False)
        except BaseException as secondary:wrapper['failureLogCollectionError']=safe_error_text(secondary, use_repr=False)
        raise
    finally:
        # Includes original failed event/identity/CLI bytes; no synthetic completion.
        target.write_text(json.dumps(wrapper,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(wrapper['verification'],sort_keys=True))


if __name__=='__main__':main()
