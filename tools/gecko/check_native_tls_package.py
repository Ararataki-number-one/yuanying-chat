#!/usr/bin/env python3
"""Inspect actual DEX definitions and merged manifests; no source-only exclusion claim."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile
from caret_build_identity import dex_definitions

ROOT=Path(__file__).resolve().parents[2]
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('integration-apk','release-apk','aapt2','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();definitions=[];manifests=[]
    for path in (args.integration_apk,args.release_apk):
        assert path.is_file() and not path.is_symlink()
        current=set()
        with ZipFile(path)as archive:
            for name in archive.namelist():
                if name.endswith('.dex'):current.update(dex_definitions(archive.read(name)))
            assert not any(name.endswith(('.key','.p12','.jks')) for name in archive.namelist())
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
               integrationApkSha256=sha(args.integration_apk),releaseApkSha256=sha(args.release_apk),testDefinitionsPresentInIntegration=True,testDefinitionsAbsentInProduction=True,testComponentsAbsentInProduction=True,keyMaterialAbsent=True,actualAndroidExecution=False,diagnosticOnly=True,releaseQualification=False)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value))
if __name__=='__main__':main()
