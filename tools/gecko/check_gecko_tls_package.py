#!/usr/bin/env python3
"""Actual merged DEX/manifest separation for the product TLS integration gate."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile
from caret_build_identity import dex_definitions
from check_native_tls_package import audit_key_entries
ROOT=Path(__file__).resolve().parents[2]
TEST_CLASSES={'Llocal/pocketchat/GeckoTlsFixtureScopes;','Llocal/pocketchat/GeckoTlsCpuIpComboIntegrationActivity;','Llocal/pocketchat/GeckoTlsCpuIpComboEvidenceProvider;','Llocal/pocketchat/GeckoTlsAcceptanceActivity;','Llocal/pocketchat/GeckoTlsAcceptanceActivity$Profile1;','Llocal/pocketchat/GeckoTlsAcceptanceActivity$Profile2;','Llocal/pocketchat/GeckoTlsAcceptanceProvider;'}
PRODUCTION_CLASSES={'Llocal/pocketchat/GeckoTls'+name+';' for name in ('Spec','Store','Ui','Controller','Profile','Native')}
ASSETS={'assets/tls-acceptance-page.js','assets/tls-acceptance-worker.js','assets/tls-cpu-ip-combo-page.js'}

def require(value,message):
    if not value:raise ValueError('Product TLS package: '+message)

def components(definitions,manifest,assets,integration):
    require(PRODUCTION_CLASSES<=definitions,'actual production TLS classes in both packages')
    if integration:
        require(TEST_CLASSES<=definitions and ASSETS<=assets,'actual integration gate class definitions and assets')
        for text in ('GeckoTlsAcceptanceActivity$Profile1','GeckoTlsAcceptanceActivity$Profile2','GeckoTlsAcceptanceProvider','local.pocketchat.test.tls-acceptance',':profile1',':profile2','GeckoTlsCpuIpComboIntegrationActivity','GeckoTlsCpuIpComboEvidenceProvider','local.pocketchat.test.gecko-tls-cpu-ip-combo-evidence',':profile6',':ip_timezone_setup'):require(text in manifest,'actual integration manifest '+text)
    else:
        require(not any(name.startswith(('Llocal/pocketchat/GeckoTlsAcceptance','Llocal/pocketchat/GeckoTlsFixtureScopes','Llocal/pocketchat/GeckoTlsCpuIpCombo')) for name in definitions) and 'GeckoTlsAcceptance' not in manifest and 'GeckoTlsCpuIpCombo' not in manifest and 'local.pocketchat.test.tls-acceptance' not in manifest and not ASSETS.intersection(assets),'no test definitions/components/assets in release')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('integration-apk','release-apk','aapt2','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();rows=[]
    for integration,path in ((True,a.integration_apk),(False,a.release_apk)):
        require(path.is_file() and not path.is_symlink(),'ordinary actual APK');definitions=set()
        with ZipFile(path) as archive:
            keys=audit_key_entries(archive,integration);names=set(archive.namelist())
            for name in names:
                if name.endswith('.dex'):definitions.update(dex_definitions(archive.read(name)))
            manifest=subprocess.check_output([str(a.aapt2),'dump','xmltree',str(path),'--file','AndroidManifest.xml'],text=True)
            components(definitions,manifest,names,integration)
            if integration:
                for name in ASSETS:require(archive.read(name)==(ROOT/'tests/gecko'/name).read_bytes(),'original integration asset bytes')
        rows.append(dict(integration=integration,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),publicSyntheticIntegrationKeyAssets=keys))
    require(not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip(),'clean selected product source')
    result=dict(schema=1,status='passed',sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceTree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip(),integrationApkSha256=rows[0]['sha256'],releaseApkSha256=rows[1]['sha256'],productionTlsDefinitionsPresentInBoth=True,testDefinitionsPresentInIntegration=True,testDefinitionsAbsentInProduction=True,testComponentsAbsentInProduction=True,testAssetsAbsentInProduction=True,keyMaterialAbsentInProduction=True,publicSyntheticIntegrationKeyAssets=rows[0]['publicSyntheticIntegrationKeyAssets'],actualAndroidExecution=False,diagnosticOnly=True,releaseQualification=False)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
