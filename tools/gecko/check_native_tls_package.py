#!/usr/bin/env python3
"""Inspect actual DEX definitions and merged manifests; no source-only exclusion claim."""
import argparse
import hashlib
import json
from pathlib import Path,PurePosixPath
import subprocess
from zipfile import ZipFile
from caret_build_identity import dex_definitions

ROOT=Path(__file__).resolve().parents[2]
# Existing public synthetic loopback PKCS#12 fixtures, never release signing keys.
# Exceptions apply only to the integration APK and require exact path, size and bytes.
PUBLIC_SYNTHETIC_INTEGRATION_KEYS={
    'assets/network-fixture.p12':(2662,'11f17bc298d59e9b2231889539375df55f60504157982982f54498363391040f'),
    'assets/native-probe-untrusted.p12':(2748,'ecaf83d9a5a53d430c4aa4579bdef64e5ce2df0a04ecd1cd8bc175d13f0cf3f8'),
    'assets/network-safe-idle-trust/server.p12':(3814,'5fe7edd5f9b89854977cc3f6181faf8b38386eb03f4829ec9d39bd3cbfb6acc3'),
}
def audit_key_entries(archive,integration):
    """No suffix-wide exception: only these pre-existing public test bytes are admitted."""
    def require(ok,reason):
        if not ok:raise ValueError('TLS package key audit: '+reason)
    names=archive.namelist();require(len(names)==len(set(names)),'duplicate archive entry')
    found={}
    for item in archive.infolist():
        name=item.filename;path=PurePosixPath(name)
        require(not path.is_absolute() and '\\'not in name and '..'not in path.parts and str(path)==name.rstrip('/'),'noncanonical archive path')
        if not name.lower().endswith(('.key','.p12','.jks')):continue
        require(integration is True and name in PUBLIC_SYNTHETIC_INTEGRATION_KEYS,'unexpected key resource or key resource in production')
        size,digest=PUBLIC_SYNTHETIC_INTEGRATION_KEYS[name]
        require(item.file_size==size,'public fixture size differs')
        raw=archive.read(item);require(len(raw)==size and hashlib.sha256(raw).hexdigest()==digest,'public fixture bytes differ')
        found[name]={'bytes':size,'sha256':digest}
    require(set(found)==(set(PUBLIC_SYNTHETIC_INTEGRATION_KEYS)if integration else set()),'exact integration fixtures required; production admits none')
    return found
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('integration-apk','release-apk','aapt2','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();definitions=[];manifests=[];key_audits=[]
    for index,path in enumerate((args.integration_apk,args.release_apk)):
        assert path.is_file() and not path.is_symlink()
        current=set()
        with ZipFile(path)as archive:
            for name in archive.namelist():
                if name.endswith('.dex'):current.update(dex_definitions(archive.read(name)))
            key_audits.append(audit_key_entries(archive,index==0))
        definitions.append(current)
        manifests.append(subprocess.check_output([str(args.aapt2),'dump','xmltree',str(path),'--file','AndroidManifest.xml'],text=True))
    required={'Llocal/pocketchat/NativeTlsProbeActivity;','Llocal/pocketchat/NativeTlsProbeProvider;'}
    assert required<=definitions[0]
    assert not any(name.startswith('Llocal/pocketchat/NativeTlsProbe')for name in definitions[1])
    assert all(name in manifests[0]for name in ('NativeTlsProbeActivity','NativeTlsProbeProvider','local.pocketchat.test.native-tls-probe',':native_tls_probe'))
    assert 'NativeTlsProbe' not in manifests[1] and 'native_tls_probe' not in manifests[1]
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    value=dict(schema=1,status='passed',sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceTree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip(),
               integrationApkSha256=sha(args.integration_apk),releaseApkSha256=sha(args.release_apk),testDefinitionsPresentInIntegration=True,testDefinitionsAbsentInProduction=True,testComponentsAbsentInProduction=True,
               unexpectedKeyMaterialAbsent=True,keyMaterialAbsentInProduction=True,publicSyntheticIntegrationKeyAssets=key_audits[0],actualAndroidExecution=False,diagnosticOnly=True,releaseQualification=False)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value))
if __name__=='__main__':main()
