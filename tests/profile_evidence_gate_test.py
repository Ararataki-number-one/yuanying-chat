"""Counterfeit metadata for negative gate tests only; nothing runs on Android."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
from profile_guard_metadata import prototype_metadata

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('profile_gate',ROOT/'tools/gecko/check_profile_evidence.py')
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)


class ProfileEvidenceGateTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name);self.source='a'*40;self.tree='b'*40
        self.files={
            'app/build.gradle':b"versionCode 51; versionName '1.6.0'",
            'tools/gecko/profile_invocation_contract.py':(ROOT/'tools/gecko/profile_invocation_contract.py').read_bytes(),
            'app/src/main/java/local/pocketchat/GeckoWebView.java':b'static final String VERSION="GeckoView 157.0.1";',
        }
        for name in gate.MODEL_INPUTS:
            self.files['app/src/main/java/local/pocketchat/'+name+'.java']=name.encode()
        proxy_paths=['app/src/main/assets/gecko/background.js','tests/browser-runtime/gecko-proxy-route.test.cjs']
        for path in proxy_paths:self.files[path]=(ROOT/path).read_bytes()
        declaration=re.search(r'const CHECK_NAMES = Object\.freeze\((\[[\s\S]*?\])\);',self.files[proxy_paths[1]].decode())
        proxy_labels=json.loads(declaration.group(1))
        paths={
            'environment-spec':'tests/gecko/EnvironmentSpecIntegrationActivity.java',
            'environment-intent':'tests/gecko/EnvironmentIntentIntegrationActivity.java',
            'environment-intent-host':'tests/environment-intent-host/local/pocketchat/EnvironmentIntentHostTest.java',
        }
        labels={}
        for name,path in paths.items():
            self.files[path]=(ROOT/path).read_bytes()
            labels[name]=re.findall(r'(?:check|rejects)\("([^"\n]+)"',self.files[path].decode())
        groups=[]
        for name in sorted(gate.HOST_GROUPS):
            if name.endswith('-host'):
                names=labels[name] if name=='environment-intent-host' else proxy_labels if name=='gecko-proxy-route-host' else ['metadata-only fixture '+str(i) for i in range(gate.MIN_HOST_COUNTS[name])]
                receipt=dict(status='passed',actualAndroidExecution=False,passed=len(names),
                    total=len(names),executed=len(names),checks=[{'name':n,'pass':True} for n in names],
                    actualCrossProcessIntentLease=True,files={})
                if name=='gecko-proxy-route-host':receipt.update(schema=1,
                    sourceCommit=self.source,sourceTree=self.tree,sourceDirty=False,
                    sourceUnchangedDuringChecks=True,actualGeckoExecution=False,
                    actualProductionScriptExecution=True,
                    files={path:hashlib.sha256(self.files[path]).hexdigest() for path in proxy_paths})
                self.write(name+'-results.json',receipt)
                groups.append(dict(test=name,report='work/profile-host/'+name+'-results.json',passed=len(names),actualAndroidExecution=False))
            else:groups.append(dict(test=name,exitCode=0,output=json.dumps({'passed':gate.MIN_HOST_COUNTS[name]})))
        self.write('profile-host-results.json',dict(status='passed',actualAndroidExecution=False,
            sourceCommit=self.source,sourceTree=self.tree,sourceDirty=False,sourceUnchangedDuringChecks=True,results=groups,
            files={path:hashlib.sha256(data).hexdigest() for path,data in self.files.items() if path.endswith(('.java','.js','.cjs'))}))
        identity=dict(schema=1,package='local.pocketchat.test',sourceCommit=self.source,sourceTree=self.tree,
            dirtySource=False,version='1.6.0',versionCode=51,sdkCoordinate='org.mozilla.geckoview:geckoview:157.0.20261005135250',
            apkBytes=100,apkSha256='c'*64,buildStampSha256='d'*64)
        for index,name in enumerate(['environment-spec','environment-intent','gecko-identity-prototype']):
            names=labels[name] if name in labels else ['metadata-only prototype']
            report=dict(schema=1,status='passed',synthetic=True,actualAndroidExecution=True,
                sourceCommit=self.source,runNonce=str(index+1)*32,buildIdentity=identity,androidSdk=35,
                passed=len(names),total=len(names),executed=len(names),checks=[{'name':n,'pass':True} for n in names])
            if name=='environment-spec':report.update(syntheticAcknowledgementsOnly=True,realAccountLogin=False,webpageFingerprintAcceptance=False)
            if name=='gecko-identity-prototype':report=prototype_metadata(identity,report['runNonce'])
            self.write_report(name,report)

    def write(self,name,value):
        (self.directory/name).write_text(json.dumps(value)+'\n')

    def write_report(self,name,report):
        self.write(name+'-results.json',report);raw=(self.directory/(name+'-results.json')).read_bytes()
        self.write(name+'-runner-log.json',dict(status='passed',sourceCommit=self.source,runNonce=report['runNonce'],
            buildIdentity=report['buildIdentity'],installedBeforeAndAfterMatched=True,rawReportPreserved=True,
            reportSha256=hashlib.sha256(raw).hexdigest(),reportBytes=len(raw),androidSdk=35,
            diagnosticOnly=name=='gecko-identity-prototype'))

    def verify(self):
        with patch.object(gate,'source_bytes',side_effect=lambda source,path:self.files[path]),patch.object(gate.subprocess,'check_output',return_value=self.tree):
            return gate.verify_profile_evidence(self.directory,self.source)

    def test_well_formed_metadata_preserves_scope(self):
        value=self.verify();self.assertFalse(value['fingerprintTemplateAcceptance']);self.assertFalse(value['realAccountLogin'])

    def test_dirty_or_wrong_source_host_cannot_pass(self):
        path=self.directory/'profile-host-results.json';value=json.loads(path.read_text())
        for edit in [dict(sourceDirty=True),dict(sourceCommit='e'*40),dict(sourceTree='f'*40),dict(sourceUnchangedDuringChecks=False)]:
            with self.subTest(edit=edit):
                self.write(path.name,dict(value,**edit))
                with self.assertRaises(ValueError):self.verify()

    def test_production_hash_mismatch_is_rejected(self):
        path=self.directory/'profile-host-results.json';value=json.loads(path.read_text())
        value['files']['app/src/main/java/local/pocketchat/NetworkChanges.java']='0'*64
        self.write(path.name,value)
        with self.assertRaises(ValueError):self.verify()

    def test_partial_intent_host_is_rejected_despite_positive_count(self):
        path=self.directory/'environment-intent-host-results.json';value=json.loads(path.read_text());value['checks']=value['checks'][:-1]
        self.write(path.name,value)
        with self.assertRaises(ValueError):self.verify()

    def test_partial_android_intent_cannot_be_rehashed_into_success(self):
        name='environment-intent';value=json.loads((self.directory/(name+'-results.json')).read_text())
        value['checks']=value['checks'][:-1];value['passed']=value['total']=value['executed']=len(value['checks'])
        self.write_report(name,value)
        with self.assertRaises(ValueError):self.verify()

    def test_raw_report_tampering_is_rejected(self):
        path=self.directory/'environment-spec-results.json';path.write_text(path.read_text()+' ')
        with self.assertRaises(ValueError):self.verify()

    def test_proxy_report_cannot_drop_shuffle_or_forge_host_scope(self):
        path=self.directory/'gecko-proxy-route-host-results.json';original=json.loads(path.read_text())
        dropped=original['checks'][:-1]
        reordered=list(original['checks']);reordered[0],reordered[1]=reordered[1],reordered[0]
        for edit in [dict(checks=dropped,total=27,executed=27,passed=27),dict(checks=reordered),
                dict(sourceDirty=True),dict(sourceUnchangedDuringChecks=False),
                dict(sourceCommit='e'*40),dict(sourceTree='f'*40),
                dict(actualAndroidExecution=True),dict(actualGeckoExecution=True),
                dict(actualProductionScriptExecution=False),dict(files={})]:
            with self.subTest(edit=edit):
                self.write(path.name,dict(original,**edit))
                with self.assertRaises(ValueError):self.verify()

    def test_proxy_production_hash_cannot_be_replaced(self):
        path=self.directory/'gecko-proxy-route-host-results.json';value=json.loads(path.read_text())
        value['files']['app/src/main/assets/gecko/background.js']='0'*64
        self.write(path.name,value)
        with self.assertRaises(ValueError):self.verify()

    def test_guard_metadata_cannot_be_rehashed_into_android_success(self):
        # Re-signing these counterfeit metadata fixtures is not Android execution.
        name='gecko-identity-prototype';original=json.loads((self.directory/(name+'-results.json')).read_text())
        from copy import deepcopy
        edits=[
            ('missing actual guard',lambda r:r.pop('guardEvidence')),
            ('new controlled connection',lambda r:r['guardEvidence']['afterServer'].update(acceptedConnections=36)),
            ('new controlled header',lambda r:r['guardEvidence'].update(afterHeaderCount=31)),
            ('untrusted worker event',lambda r:r['guardEvidence']['observed']['worker'].update(trusted=False)),
            ('foreign native sender',lambda r:r['guardEvidence']['nativePort'].update(nativeSession=5002)),
            ('Java boolean arm flag',lambda r:r['guardEvidence'].update(armCallback=True)),
            ('dropped route evidence',lambda r:r['guardEvidence'].update(blockedRoutesDropped=1)),
        ]
        for label,edit in edits:
            with self.subTest(label=label):
                value=deepcopy(original);edit(value);self.write_report(name,value)
                with self.assertRaises(ValueError):self.verify()


if __name__=='__main__':unittest.main()
