#!/usr/bin/env python3
"""Read-only actual SDK verification plus the exact production fresh-signer policy."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/gecko'))
from native_input_contract import decode


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home',type=Path,default=os.environ.get('JAVA_HOME'))
    parser.add_argument('--apksigner-jar',type=Path,default=Path(os.environ.get('ANDROID_HOME','/missing'))/'build-tools/37.0.0/lib/apksigner.jar')
    parser.add_argument('--signed-apk',type=Path,default=ROOT/'app/build/outputs/apk/integration/app-x86_64-integration.apk')
    parser.add_argument('--unsigned-apk',type=Path,default=ROOT/'app/build/outputs/apk/release/app-arm64-v8a-release-unsigned.apk')
    parser.add_argument('--output',type=Path,default=ROOT/'work/gecko-integration/native-input-signature-api-host-results.json')
    args=parser.parse_args();out=args.output;out.parent.mkdir(parents=True,exist_ok=True)
    evidence=out.parent;raw_paths=[]
    report=dict(status='failed',actualAndroidExecution=False,releaseAcceptance=False,
        scope='Read-only SDK 37 verification of existing APKs and tampered copy; policy facts are synthetic',
        invocationIdentityScope='Host invocation metadata; not the original CI driver signature evidence',cases=[])
    def run(label,command):
        result=subprocess.run([str(x) for x in command],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        for stream in ('stdout','stderr'):
            path=evidence/('native-input-signature-api-host-'+label+'-'+stream+'.log');path.write_bytes(getattr(result,stream));raw_paths.append(path)
        return result
    try:
        if args.java_home is None:raise ValueError('JDK17 is required; no skip')
        java=args.java_home/'bin/java';javac=args.java_home/'bin/javac';jar=args.apksigner_jar.resolve()
        verifier=ROOT/'tools/gecko/VerifyNativeInputSignature.java';host=ROOT/'tests/native-input-signature-host/SignaturePolicyHost.java'
        for path in (java,javac,jar,args.signed_apk,args.unsigned_apk,verifier,host):
            if not path.is_file():raise ValueError('Missing required actual input: '+str(path))
        before={str(p.resolve()):sha(p) for p in (jar,args.signed_apk,args.unsigned_apk,verifier,host)}
        report['inputs']=before
        source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip()
        run_id=os.environ.get('GITHUB_RUN_ID','0');attempt=os.environ.get('GITHUB_RUN_ATTEMPT','0')
        report['invocationIdentity']=dict(sourceCommit=source,sourceTree=tree,runId=run_id,runAttempt=attempt,
            dirtySource=bool(subprocess.check_output(['git','status','--porcelain','--untracked-files=normal'],cwd=ROOT)))
        with tempfile.TemporaryDirectory(prefix='native-signature-api-') as folder:
            work=Path(folder);classes=work/'classes';classes.mkdir()
            compiled=run('compile',[javac,'-encoding','UTF-8','-cp',jar,'-d',classes,verifier,host]);compiled.check_returncode()
            classpath=str(classes)+os.pathsep+str(jar)
            policy=run('policy',[java,'-cp',classpath,'SignaturePolicyHost']);policy.check_returncode()
            report['productionPolicy']=decode(policy.stdout)
            if report['productionPolicy']['status']!='passed':raise ValueError('Production policy checks failed')
            damaged=work/'tampered.apk';damaged.write_bytes(args.signed_apk.read_bytes())
            with zipfile.ZipFile(args.signed_apk) as archive:
                info=archive.getinfo('classes.dex')
                with damaged.open('r+b') as target:
                    target.seek(info.header_offset);header=target.read(30)
                    name_length,extra_length=struct.unpack_from('<HH',header,26)
                    target.seek(info.header_offset+30+name_length+extra_length+max(0,info.compress_size//2))
                    byte=target.read(1)
                    if len(byte)!=1:raise ValueError('No payload byte to corrupt')
                    target.seek(-1,1);target.write(bytes([byte[0]^1]))
            for label,apk,expected in [('signed',args.signed_apk,True),('unsigned',args.unsigned_apk,False),('tampered',damaged,False)]:
                actual=run(label,[java,'-cp',classpath,'VerifyNativeInputSignature',apk,verifier,source,tree,run_id,attempt])
                value=decode(actual.stdout)
                report['cases'].append(dict(name=label,returnCode=actual.returncode,apkSha256=sha(apk),
                    expectedAcceptance=expected,result=value))
                accepted=actual.returncode==0 and value.get('status')=='passed'
                if accepted!=expected:raise ValueError('Unexpected actual API acceptance: '+label)
                if value.get('apkSha256')!=sha(apk) or value.get('apksignerJarSha256')!=sha(jar):raise ValueError('Actual API input identity differs')
                if expected and (value.get('loadedApksignerJarPath')!=str(jar) or not value.get('inputsUnchangedDuringVerification')):
                    raise ValueError('Loaded verifier identity differs')
        report['sourceInputsUnchanged']=all(sha(Path(path))==digest for path,digest in before.items())
        if not report['sourceInputsUnchanged']:raise ValueError('Read-only input changed')
        report['status']='passed'
    except Exception as failure:
        report['error']=type(failure).__name__+': '+str(failure)
        raise
    finally:
        report['rawOutputs']={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(raw_paths)}
        out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],actualApiCases=len(report['cases']),policyChecks=report['productionPolicy']['checkCount'])))


if __name__=='__main__':main()
