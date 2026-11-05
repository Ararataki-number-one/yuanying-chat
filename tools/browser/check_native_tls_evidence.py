#!/usr/bin/env python3
"""Replay exact selected-source standalone native TLS diagnostic evidence."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/gecko"))
from native_tls_probe_contract import equal, strict_json, validate_native_tls, require
from profile_invocation_contract import verify_installed


def source_bytes(source, path):
    require(type(path) is str and path.startswith(("app/", "tests/", "tools/", ".github/")) and ".." not in Path(path).parts, "selected source path")
    return subprocess.check_output(["git", "show", source + ":" + path], cwd=ROOT)


def verify_native_tls_evidence(directory, source, *, reader=source_bytes):
    directory = Path(directory)
    require(type(source) is str and re.fullmatch("[0-9a-f]{40}", source), "exact selected source commit")
    path = directory / "results.json"
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 2 * 1024 * 1024, "bounded ordinary host result")
    # Keep duplicate-key/type validation at the same strict parser boundary for the larger source-pin table.
    raw = path.read_bytes()
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate host JSON key")
            result[key] = value
        return result
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
    require(type(value) is dict and type(value.get("schema")) is int and value["schema"] == 1 and value.get("kind") == "native-tls-probe-v1" and value.get("status") == "passed", "successful complete diagnostic")
    require(value.get("sourceCommit") == source and type(value.get("sourceTree")) is str and re.fullmatch("[0-9a-f]{40}", value["sourceTree"]), "actual source/tree")
    require(subprocess.check_output(["git", "rev-parse", source + "^{tree}"], cwd=ROOT, text=True).strip() == value["sourceTree"], "selected Git tree differs")
    for key in ("diagnosticOnly", "standaloneSessionCapabilityOnly", "actualAndroidExecution", "actualGeckoExecution", "executionInputsUnchanged"):
        require(value.get(key) is True, "scope/actual execution: " + key)
    for key in ("releaseQualification", "beforePhase1Qualified", "fullTlsFingerprintEmulation", "quicWireVerified"):
        require(value.get(key) is False, "bounded diagnostic scope: " + key)
    for key in ("runId", "runAttempt"):
        require(type(value.get(key)) is str and re.fullmatch("[1-9][0-9]*", value[key]), "actual run identity")
    require(value.get("errors") == [] and type(value.get("cleanup")) is dict and set(value["cleanup"]) == {"appStopped", "appDataCleared", "reverseRemoved", "caRemoved", "privateMaterialRemoved", "shellUidRestored"} and all(item is True for item in value["cleanup"].values()), "all exact cleanup requirements")
    require(value.get("nativeReport") == "native-report.json", "fixed native report file")
    native_path = directory / "native-report.json"
    require(native_path.is_file() and not native_path.is_symlink(), "ordinary original device report")
    native_raw = native_path.read_bytes()
    require(hashlib.sha256(native_raw).hexdigest() == value.get("nativeReportSha256"), "original native bytes hash")
    native = strict_json(native_raw)
    identity = value.get("expectedBuildIdentity")
    require(type(identity) is dict and identity.get("sourceCommit") == source and identity.get("sourceTree") == value["sourceTree"], "expected APK source")
    verify_installed(native.get("buildIdentity", {}), identity)
    sdk = identity.get("sdkBuildIdentity", {})
    require(sdk.get("runId") == value["runId"] and sdk.get("runAttempt") == value["runAttempt"], "SDK run differs from actual diagnostic")
    tls = value.get("hostTls")
    require(type(tls) is dict and tls.get("privateMaterialExported") is False and tls.get("certificateExceptionUsed") is False and tls.get("ephemeral") is True and tls.get("privateMaterialRemoved") is True, "ephemeral controlled TLS material")
    binding = tls.get("binding")
    require(type(binding) is dict and binding == dict(sourceCommit=source, sourceTree=value["sourceTree"], runNonce=value.get("runNonce"), integrationApkSha256=identity.get("apkSha256")), "wire/APK/source binding")
    trust = tls.get("trustInstallation", {})
    require(trust.get("method") == "domain-scoped-user-ca" and trust.get("installedPublicCaBytesMatch") is True and trust.get("removedAfterExecution") is True and trust.get("shellRestoredAfterCleanup") is True and trust.get("publicCaPemSha256") == tls.get("caPemSha256") and trust.get("expectedLeafDerSha256") == tls.get("leafDerSha256"), "actual scoped CA install/cleanup binding")
    checked = validate_native_tls(native, value.get("host"), run=value.get("runNonce"), source=source, tree=value["sourceTree"], leaf=tls.get("leafDerSha256"))
    require(equal(checked, value.get("checked")), "stored host conclusion differs from original wire/device bytes")
    files = value.get("sourceFiles")
    required = {"tests/gecko/NativeTlsProbeActivity.java", "tests/gecko/NativeTlsProbeProvider.java", "tests/gecko/AndroidManifest.xml", "tools/browser/native_tls_probe_server.py", "tools/browser/fingerprint_fixture_server.py", "tools/browser/check_native_tls_evidence.py", "tools/gecko/native_tls_probe_contract.py", "tools/gecko/run_native_tls_probe.py", ".github/workflows/native-tls-probe.yml"}
    require(type(files) is dict and required <= set(files) and 1000 <= len(files) <= 5000, "complete selected source pins")
    expected_names=set(subprocess.check_output(["git", "ls-tree", "-r", "--name-only", source, "--", "app", "tests", "tools", ".github"],cwd=ROOT,text=True).splitlines())
    require(set(files)==expected_names,"selected source table must be complete")
    executable_paths=("tools/browser/check_native_tls_evidence.py","tools/gecko/native_tls_probe_contract.py","tools/browser/native_tls_probe_server.py","tools/gecko/profile_invocation_contract.py","tools/gecko/sdk_identity_contract.py")
    for name in executable_paths:
        require((ROOT/name).read_bytes()==reader(source,name),"executed validator must equal selected immutable source: "+name)
    for name, digest in files.items():
        require(type(digest) is str and re.fullmatch("[0-9a-f]{64}", digest) and hashlib.sha256(reader(source, name)).hexdigest() == digest, "selected source pin differs: " + name)
    return dict(schema=1, status="passed", sourceCommit=source, sourceTree=value["sourceTree"], runId=value["runId"], runAttempt=value["runAttempt"], integrationApkSha256=identity["apkSha256"],
                originalNativeReportSha256=value["nativeReportSha256"], hostReportSha256=hashlib.sha256(raw).hexdigest(), sourcePinsChecked=len(files), checked=checked,
                actualAndroidExecution=True, actualGeckoExecution=True, standaloneSessionCapabilityOnly=True, fullTlsFingerprintEmulation=False, quicWireVerified=False, releaseQualification=False)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory", type=Path)
    p.add_argument("--source", required=True)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    report = verify_native_tls_evidence(a.directory, a.source)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("status", "sourceCommit", "sourcePinsChecked", "releaseQualification")}))
