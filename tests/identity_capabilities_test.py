#!/usr/bin/env python3
"""Failure-oriented contract tests. Test receipts are explicitly synthetic fixtures."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("identity_contract", ROOT / "tools/gecko/check_identity_capabilities.py")
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)


class IdentityContractTest(unittest.TestCase):
    def test_official_inventory(self):
        manifest = json.loads((ROOT / "third-party/sdk/identity-capabilities.json").read_text())
        self.assertFalse(contract.check_official(ROOT, manifest)["nativeControlsEnabled"])
        for mutation in ("verified", "enabled", "prototype", "unsupported-but-enabled"):
            bad = copy.deepcopy(manifest)
            bad["capabilities"]["INDEPENDENT_TIMEZONE"] = mutation
            with self.assertRaises(contract.ContractError):
                contract.check_official(ROOT, bad)
        manifest["actualAndroidExecution"] = True
        with self.assertRaises(contract.ContractError):
            contract.check_official(ROOT, manifest)

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
