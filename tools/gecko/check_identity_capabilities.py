#!/usr/bin/env python3
"""Read-only identity inventory/prototype provenance checks; never enable a native feature.

Passing this contract is evidence consistency, not independent proof that a device
test happened. The shipped Java backend remains official until explicitly replaced.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
CAPABILITIES = {"INDEPENDENT_TIMEZONE", "CANVAS_READBACK", "WEBGL_IDENTITY", "AUDIO_IDENTITY", "FONT_IDENTITY"}
CONTEXTS = {"page-main", "same-origin-frame", "cross-origin-frame", "dedicated-worker", "shared-worker", "service-worker"}
NATIVE_GATES = {"environment-isolation", "restart-persistence", "chatgpt-compatibility", "resource-budget", "upstream-rebase", "configuration-fallback"}
ORIGINAL_SIGNER = "f0afa2ef2b9ac68020b374276318b12d2bb4de65d2a3b788194de551356b9434"


class ContractError(ValueError):
    pass


def require(value, message):
    if not value:
        raise ContractError(message)


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def source_sha(value, label):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value), label + " must be a complete revision.")


def safe_path(root, value):
    require(isinstance(value, str) and value and not Path(value).is_absolute(), "Artifact paths must be repository-relative.")
    path = (root / value).resolve()
    require(path.is_relative_to(root.resolve()), "Artifact path escapes the repository.")
    require(path.is_file(), "Missing artifact: " + value)
    return path


def blob(root, record, label):
    require(isinstance(record, dict), label + " requires an artifact record.")
    path = safe_path(root, record.get("path"))
    require(type(record.get("bytes")) is int and record["bytes"] > 0 and path.stat().st_size == record["bytes"], label + " byte count differs.")
    require(isinstance(record.get("sha256"), str) and re.fullmatch(r"[0-9a-f]{64}", record["sha256"]), label + " requires SHA-256.")
    require(digest(path) == record["sha256"], label + " SHA-256 differs.")
    return path


def gradle_identity(root):
    text = (root / "app/build.gradle").read_text(encoding="utf-8")
    dependencies = re.findall(r"implementation\s+'(org\.mozilla\.geckoview:[^']+)'", text)
    require(len(dependencies) == 1, "Exactly one Gecko SDK dependency is required.")
    version = re.search(r"versionName '([0-9]+\.[0-9]+\.[0-9]+)'", text)
    code = re.search(r"versionCode ([0-9]+)", text)
    require(version and code, "Missing app version metadata.")
    return dependencies[0], version.group(1), int(code.group(1))


def check_official(root, manifest, aar=None):
    require(manifest.get("schema") == 1 and manifest.get("engineMode") == "official", "Shipped inventory must describe the official backend.")
    receipt = json.loads(safe_path(root, manifest.get("sdkReceipt")).read_text())
    coordinate, _, _ = gradle_identity(root)
    require(coordinate == manifest.get("coordinate") == receipt.get("coordinate"), "Inventory/Gradle/receipt SDK coordinates differ.")
    require(receipt.get("sdkAarModified") is False and receipt.get("sdkClassTransformApplied") is False, "Official SDK receipt cannot claim native modifications.")
    require(manifest.get("upstreamRevision") == receipt.get("upstreamRevision"), "Inventory upstream revision differs.")
    require(manifest.get("aarSha256") == receipt.get("aar", {}).get("sha256"), "Inventory AAR hash differs.")
    source_sha(manifest.get("upstreamRevision"), "Upstream revision")
    require(manifest.get("actualAndroidExecution") is False, "Build inventory must not claim Android execution.")
    capabilities = manifest.get("capabilities")
    require(isinstance(capabilities, dict) and set(capabilities) == CAPABILITIES, "Native capability inventory is incomplete.")
    require(all(status == "unsupported" for status in capabilities.values()), "Official backend must not claim unimplemented independent native controls.")
    java = (root / "app/src/main/java/local/pocketchat/NativeCapabilityManifest.java").read_text()
    for key, expected in (("SDK_COORDINATE", coordinate), ("UPSTREAM_REVISION", manifest["upstreamRevision"]), ("AAR_SHA256", manifest["aarSha256"])):
        require(re.search(r'\b' + key + r'\s*=\s*"' + re.escape(expected) + r'"', java), "Java native inventory differs: " + key)
    require("enum Status { UNSUPPORTED }" in java, "New native support states require a reviewed backend and validator update.")
    if aar is not None:
        require(aar.stat().st_size == receipt["aar"]["bytes"] and digest(aar) == manifest["aarSha256"], "Resolved AAR differs from official inventory.")
    return {"status": "passed", "engineMode": "official", "coordinate": coordinate,
            "upstreamRevision": manifest["upstreamRevision"], "aarSha256": manifest["aarSha256"],
            "resolvedAarChecked": aar is not None, "actualAndroidExecution": False,
            "nativeControlsEnabled": False, "scope": "Build inventory only; runtime support remains unsupported."}


def check_prototype(root, manifest):
    require(manifest.get("schema") == 1 and manifest.get("engineMode") == "patched-prototype", "Custom core input must be explicitly marked patched-prototype.")
    require(manifest.get("productionEnabled") is False, "Prototype validation cannot enable production native controls.")
    require(manifest.get("sdkAarModified") is True, "Patched core must not be described as an unmodified official AAR.")
    source_sha(manifest.get("upstreamRevision"), "Prototype upstream")
    source_sha(manifest.get("rebasedUpstreamRevision"), "Rebased upstream")
    source_sha(manifest.get("sourceCommit"), "Prototype app source")
    require(manifest["upstreamRevision"] != manifest["rebasedUpstreamRevision"], "At least one newer upstream rebase is required.")
    capabilities = manifest.get("capabilities")
    require(isinstance(capabilities, list) and capabilities and set(capabilities) <= CAPABILITIES and len(set(capabilities)) == len(capabilities), "Prototype capabilities must be explicit and unique.")
    require(manifest.get("builtAbis") == ["arm64-v8a"], "Initial native prototype must include an explicitly tested ARM64 build.")
    patches = manifest.get("patches")
    require(isinstance(patches, list) and patches, "Ordered native patch artifacts are required.")
    for i, patch in enumerate(patches):
        blob(root, patch, "Patch " + str(i))
    require(len({patch["path"] for patch in patches}) == len(patches), "Patch entries must not repeat.")
    blob(root, manifest.get("buildRecipe"), "Build recipe")
    blob(root, manifest.get("aar"), "Custom AAR")
    blob(root, manifest.get("buildLog"), "Build log")
    report_path = blob(root, manifest.get("deviceEvidence"), "Device evidence")
    report = json.loads(report_path.read_text())
    require(report.get("schema") == 1 and report.get("status") == "passed", "Native device report must pass.")
    require(report.get("actualAndroidExecution") is True and report.get("physicalDevice") is True
            and report.get("releaseMode") is True and report.get("synthetic") is False, "Synthetic/emulator/host evidence cannot accept a native device capability.")
    require(report.get("sourceCommit") == manifest["sourceCommit"] and report.get("engineAarSha256") == manifest["aar"]["sha256"]
            and report.get("upstreamRevision") == manifest["rebasedUpstreamRevision"], "Device evidence is not bound to the prototype build.")
    require(report.get("abi") == "arm64-v8a" and isinstance(report.get("deviceModel"), str) and report["deviceModel"].strip(), "A real ARM device identity is required.")
    records = report.get("checks")
    require(isinstance(records, list) and records and all(isinstance(item, dict) and item.get("pass") is True for item in records), "All native checks must pass.")
    for capability in capabilities:
        require(CONTEXTS <= {item.get("context") for item in records if item.get("capability") == capability}, "Missing execution contexts for " + capability)
    require(NATIVE_GATES <= {item.get("name") for item in records}, "Missing isolation, persistence, compatibility, resource, rebase or fallback gate.")
    for item in records:
        blob(root, item.get("observation"), "Measured observation")
    return {"status": "passed", "engineMode": "patched-prototype", "nativeControlsEnabled": False,
            "prototypeEvidenceConsistent": True, "scope": "Artifact/report consistency only. Backend integration and independent acceptance remain required."}


def check_release(root, manifest, source, apk=None):
    _, version, code = gradle_identity(root)
    source_sha(source, "Release source")
    require(manifest.get("version") == version and manifest.get("versionCode") == code, "Release version differs from app metadata.")
    require(manifest.get("sourceCommit") == source, "Release report belongs to a different source.")
    require(manifest.get("signerSha256") == ORIGINAL_SIGNER, "Release signer differs from the established application.")
    require(manifest.get("filename") == "PocketChat-" + version + "-gecko-arm64.apk", "Release APK name differs.")
    if apk is not None:
        require(apk.stat().st_size == manifest.get("bytes") and digest(apk) == manifest.get("sha256"), "Release APK bytes differ.")
    return {"status": "passed", "version": version, "versionCode": code, "sourceCommit": source,
            "apkBytesChecked": apk is not None, "scope": "Release metadata consistency; signer value is not cryptographic signature verification."}


def check_resource_budget(root, manifest):
    require(manifest.get("schema") == 1 and manifest.get("status") == "passed", "Resource measurement must pass.")
    require(manifest.get("actualAndroidExecution") is True and manifest.get("physicalDevice") is True
            and manifest.get("synthetic") is False, "Resource capacity cannot be inferred from host or emulator checks.")
    source_sha(manifest.get("sourceCommit"), "Resource test source")
    require(isinstance(manifest.get("deviceScope"), str) and manifest["deviceScope"].strip(), "Measured device scope is required.")
    official = json.loads((root / "third-party/sdk/identity-capabilities.json").read_text())
    require(manifest.get("engineRevision") == official["upstreamRevision"]
            and manifest.get("engineAarSha256") == official["aarSha256"], "Resource budget belongs to another engine build.")
    maximum = manifest.get("maximumLive")
    require(type(maximum) is int and 1 <= maximum <= 8, "Measured capacity must be between one and eight saved slots.")
    require(type(manifest.get("minimumAvailableBytes")) is int and manifest["minimumAvailableBytes"] >= 0, "A measured memory threshold is required.")
    runs = manifest.get("runs")
    require(isinstance(runs, list) and runs, "Real resource measurement runs are required.")
    required = {"foreground-input", "long-reply", "upload", "download", "background-restore"}
    verified = set()
    for run in runs:
        require(isinstance(run, dict) and run.get("pass") is True, "All resource measurement runs must pass.")
        require(type(run.get("liveCount")) is int and 1 <= run["liveCount"] <= 8, "Run live count is invalid.")
        require(type(run.get("durationSeconds")) is int and run["durationSeconds"] >= 120, "Resource run is too short to define a budget.")
        blob(root, run.get("observation"), "Resource measurements")
        if run["liveCount"] == maximum:
            verified.add(run.get("scenario"))
    require(required <= verified, "Capacity must be measured across input, reply, upload, download and background restoration.")
    return {"status": "passed", "deviceScope": manifest["deviceScope"], "maximumLive": maximum,
            "admissionEnabled": False, "scope": "Device-specific report consistency; never an eight-environment universal capacity claim."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--aar", type=Path)
    parser.add_argument("--prototype", type=Path)
    parser.add_argument("--release-manifest", type=Path)
    parser.add_argument("--resource-budget", type=Path)
    parser.add_argument("--source")
    parser.add_argument("--apk", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        manifest = json.loads((args.manifest or root / "third-party/sdk/identity-capabilities.json").read_text())
        result = {"inventory": check_official(root, manifest, args.aar)}
        if args.prototype:
            result["prototype"] = check_prototype(root, json.loads(args.prototype.read_text()))
        if args.resource_budget:
            result["resourceBudget"] = check_resource_budget(root, json.loads(args.resource_budget.read_text()))
        if args.release_manifest:
            source = args.source or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            result["release"] = check_release(root, json.loads(args.release_manifest.read_text()), source, args.apk)
        require(args.apk is None or args.release_manifest is not None, "--apk requires --release-manifest.")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ContractError, OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        parser.exit(1, "Identity capability validation failed: " + str(error) + "\n")


if __name__ == "__main__":
    main()
