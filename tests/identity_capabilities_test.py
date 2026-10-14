#!/usr/bin/env python3
"""Failure-oriented contract tests. Test receipts are explicitly synthetic fixtures."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools/gecko"))
spec = importlib.util.spec_from_file_location("identity_contract", ROOT / "tools/gecko/check_identity_capabilities.py")
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)


class IdentityContractTest(unittest.TestCase):
    def test_official_inventory(self):
        # Preserve the real historical official source contract in an explicit
        # frozen fixture; the current derived backend must not impersonate it.
        frozen=ROOT/'tests/sdk-provenance-fixtures/official-157'
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for path,material in (('app/build.gradle',frozen/'app-build.gradle'),('app/src/main/java/local/pocketchat/NativeCapabilityManifest.java',frozen/'NativeCapabilityManifest.java'),('third-party/sdk/identity-capabilities.json',frozen/'identity-capabilities.json'),('third-party/sdk/geckoview-157.0.1-official.json',ROOT/'third-party/sdk/geckoview-157.0.1-official.json')):
                destination=root/path;destination.parent.mkdir(parents=True,exist_ok=True)
                destination.write_bytes(material.read_bytes())
            manifest=json.loads((root/'third-party/sdk/identity-capabilities.json').read_text())
            self.assertFalse(contract.check_official(root,manifest)['nativeControlsEnabled'])
            for mutation in ('verified','enabled','prototype','unsupported-but-enabled'):
                bad=copy.deepcopy(manifest);bad['capabilities']['INDEPENDENT_TIMEZONE']=mutation
                with self.assertRaises(contract.ContractError):contract.check_official(root,bad)
            manifest['actualAndroidExecution']=True
            with self.assertRaises(contract.ContractError):contract.check_official(root,manifest)

    def test_derived_inventory_requires_selected_source_and_keeps_native_controls_unsupported(self):
        from profile_sdk_identity_test import fixture, SOURCE, sdk
        selected,materials,reader,_,_,_,_,_=fixture()
        materials['app/src/main/java/local/pocketchat/NativeCapabilityManifest.java']=(ROOT/'app/src/main/java/local/pocketchat/NativeCapabilityManifest.java').read_bytes()
        def git_output(arguments,**kwargs):
            if arguments==['git','rev-parse','HEAD']:return SOURCE+'\n'
            if arguments[:2]==['git','show']:return reader(*arguments[2].split(':',1))
            raise AssertionError('Unexpected source query: '+repr(arguments))
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'app').mkdir();(root/'app/build.gradle').write_text("implementation '"+sdk.SDK_RUNTIME_COORDINATE+"'; versionName '2.0.0'; versionCode 53")
            manifest=dict(schema=1,engineMode='source-derived-java',coordinate=sdk.SDK_RUNTIME_COORDINATE,sdkInputCoordinate=sdk.SDK_COORDINATE,sdkReceipt=sdk.DERIVED_MANIFEST,sdkReceiptSha256=sdk.digest(materials[sdk.DERIVED_MANIFEST]),aarSha256=selected['sdkAarSha256'],upstreamRevision=selected['upstreamRevision'],actualAndroidExecution=False,capabilities={name:'unsupported' for name in contract.CAPABILITIES})
            with patch.object(contract.subprocess,'check_output',side_effect=git_output):
                self.assertFalse(contract.check_source_derived_input(root,manifest)['nativeControlsEnabled'])
                for key,value in (('engineMode','official'),('coordinate',sdk.SDK_COORDINATE),('aarSha256',sdk.SDK_AAR_SHA256),('sdkReceiptSha256','0'*64),('actualAndroidExecution',True)):
                    with self.subTest(field=key),self.assertRaises(contract.ContractError):contract.check_source_derived_input(root,dict(manifest,**{key:value}))
                for capability in contract.CAPABILITIES:
                    bad=copy.deepcopy(manifest);bad['capabilities'][capability]='verified'
                    with self.subTest(capability=capability),self.assertRaises(contract.ContractError):contract.check_source_derived_input(root,bad)

    def test_path_escape_and_hash_tamper(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "patch").write_text("prototype")
            sha = hashlib.sha256(b"prototype").hexdigest()
            receipt = {"path": "patch", "bytes": 9, "sha256": sha}
            self.assertEqual(contract.blob(root, receipt, "patch"), root / "patch")
            with self.assertRaises(contract.ContractError):
                contract.blob(root, dict(receipt, sha256="0" * 64), "patch")
            with self.assertRaises(contract.ContractError):
                contract.safe_path(root, "../outside")
            with self.assertRaises(contract.ContractError):
                contract.safe_path(root, "/tmp")

    def fixture(self, root):
        def record(name, content):
            data = content.encode()
            (root / name).write_bytes(data)
            return {"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        source = "a" * 40
        upstream = "b" * 40
        aar = record("custom.aar", "synthetic-test-artifact")
        observation = record("observation.json", '{"fixture":true}')
        checks = [{"capability": "INDEPENDENT_TIMEZONE", "context": context, "pass": True, "observation": observation} for context in contract.CONTEXTS]
        checks += [{"name": name, "pass": True, "observation": observation} for name in contract.NATIVE_GATES]
        report = {"schema":1,"status":"passed","actualAndroidExecution":True,"physicalDevice":True,
                  "releaseMode":True,"synthetic":False,"sourceCommit":source,"engineAarSha256":aar["sha256"],
                  "upstreamRevision":upstream,"abi":"arm64-v8a","deviceModel":"contract-fixture","checks":checks}
        # Fixtures exercise only report structure. They are not shipped or runtime evidence.
        manifest = {"schema":1,"engineMode":"patched-prototype","productionEnabled":False,"sdkAarModified":True,
                    "upstreamRevision":"c"*40,"rebasedUpstreamRevision":upstream,"sourceCommit":source,
                    "builtAbis":["arm64-v8a"],"capabilities":["INDEPENDENT_TIMEZONE"],
                    "patches":[record("test.patch","test-only-patch")],"buildRecipe":record("recipe","test-only-recipe"),
                    "buildLog":record("log","test-only-log"),"aar":aar,"deviceEvidence":record("evidence.json",json.dumps(report))}
        return manifest, report, record

    def test_prototype_never_enables_and_rejects_host_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest, report, record = self.fixture(root)
            self.assertFalse(contract.check_prototype(root, manifest)["nativeControlsEnabled"])
            for field, value in (("synthetic",True),("physicalDevice",False),("actualAndroidExecution",False),
                                 ("releaseMode",False),("sourceCommit","d"*40),("engineAarSha256","e"*64),("abi","x86_64")):
                bad_report = dict(report, **{field:value})
                bad = dict(manifest, deviceEvidence=record("bad.json",json.dumps(bad_report)))
                with self.subTest(field=field), self.assertRaises(contract.ContractError):
                    contract.check_prototype(root, bad)

    def test_prototype_requires_rebase_contexts_and_all_gates(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest, report, record = self.fixture(root)
            for bad in (dict(manifest,productionEnabled=True),dict(manifest,sdkAarModified=False),
                        dict(manifest,rebasedUpstreamRevision=manifest["upstreamRevision"]),dict(manifest,patches=[])):
                with self.assertRaises(contract.ContractError):
                    contract.check_prototype(root, bad)
            for predicate in (lambda c:c.get("context")!="cross-origin-frame",lambda c:c.get("name")!="configuration-fallback"):
                bad_report = dict(report, checks=[c for c in report["checks"] if predicate(c)])
                bad = dict(manifest,deviceEvidence=record("bad.json",json.dumps(bad_report)))
                with self.assertRaises(contract.ContractError):
                    contract.check_prototype(root, bad)

    def test_release_version_source_signer_and_bytes(self):
        _, version, code = contract.gradle_identity(ROOT)
        manifest = {"version":version,"versionCode":code,"sourceCommit":"a"*40,
                    "signerSha256":contract.ORIGINAL_SIGNER,"filename":"PocketChat-"+version+"-gecko-arm64.apk"}
        self.assertEqual(contract.check_release(ROOT,manifest,"a"*40)["versionCode"],code)
        for key, value in (("versionCode",code+1),("version","0.0.0"),("sourceCommit","b"*40),("signerSha256","c"*64)):
            with self.subTest(key=key), self.assertRaises(contract.ContractError):
                contract.check_release(ROOT,dict(manifest,**{key:value}),"a"*40)

    def test_measured_capacity_requires_physical_matching_engine_and_scenarios(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            identity = json.loads((ROOT / "third-party/sdk/identity-capabilities.json").read_text())
            (root / "third-party/sdk").mkdir(parents=True)
            (root / "third-party/sdk/identity-capabilities.json").write_text(json.dumps(identity))
            raw = b'{"fixture":true}'
            (root / "samples.json").write_bytes(raw)
            observation = {"path":"samples.json","bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}
            report = {"schema":1,"status":"passed","actualAndroidExecution":True,"physicalDevice":True,"synthetic":False,
                      "sourceCommit":"a"*40,"deviceScope":"contract-fixture","engineRevision":identity["upstreamRevision"],
                      "engineAarSha256":identity["aarSha256"],"maximumLive":2,"minimumAvailableBytes":0,
                      "runs":[{"pass":True,"liveCount":2,"durationSeconds":120,"scenario":scenario,"observation":observation}
                              for scenario in ("foreground-input","long-reply","upload","download","background-restore")]}
            self.assertFalse(contract.check_resource_budget(root,report)["admissionEnabled"])
            for key, value in (("synthetic",True),("physicalDevice",False),("actualAndroidExecution",False),
                               ("engineRevision","b"*40),("maximumLive",8),("maximumLive",9)):
                with self.subTest(key=key), self.assertRaises(contract.ContractError):
                    contract.check_resource_budget(root,dict(report,**{key:value}))
            bad = copy.deepcopy(report)
            bad["runs"][0]["durationSeconds"] = 1
            with self.assertRaises(contract.ContractError):
                contract.check_resource_budget(root,bad)


if __name__ == "__main__":
    unittest.main()
