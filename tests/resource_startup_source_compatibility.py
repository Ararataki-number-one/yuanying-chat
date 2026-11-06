"""Strict finite historical metadata for actual asynchronous resource recovery.

Production, device fixtures, SDK compilation and behavior hosts read current
bytes. These views only compose the original whole-source historical oracles.
"""
import copy
import hashlib
import json
import re
from pathlib import Path

GV = "app/src/main/java/local/pocketchat/GeckoWebView.java"
FINAL = "tests/final_browser_source_compatibility.py"
LAYER = "tests/profile_fixture_root_source_compatibility.py"
FINALTEST = "tests/profile_final_browser_source_compatibility_test.py"
ROOTTEST = "tests/profile_fixture_root_source_compatibility_test.py"
SOURCE_PATHS = (GV, FINAL, LAYER, FINALTEST, ROOTTEST)
CONFIG = Path(__file__).resolve().parent / "fixtures/resource-startup-source-deltas.json"
CONFIG_SHA256 = "417f15a681f3fcf0bf29f4370a76b489e79a78f16f0e99d768e2fad73a9605a0"

def _sha(raw):
    return hashlib.sha256(raw).hexdigest()

def _encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()

def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate resource metadata member")
        value[key] = item
    return value

def _nonfinite(value):
    raise ValueError("Nonfinite resource metadata member")

def config():
    if CONFIG.is_symlink() or not CONFIG.is_file() or CONFIG.resolve() != CONFIG.absolute():
        raise ValueError("Resource metadata requires its ordinary exact fixture")
    raw = CONFIG.read_bytes()
    if not 0 < len(raw) <= 256*1024 or _sha(raw) != CONFIG_SHA256:
        raise ValueError("Resource metadata fixture differs from reviewed bytes")
    value = json.loads(raw, object_pairs_hook=_unique, parse_constant=_nonfinite)
    if (type(value) is not dict or set(value) != {"schema", "kind", "productionBaseCommit", "localMetadataParent", "actualAndroidExecution", "runtimeAcceptance", "finalFixtureSha256", "finalAfterSha256", "finalBefore", "finalAfter", "rootBeforeSha256", "rootAfterRow", "sources"}
            or value.get("schema") != 1 or type(value.get("schema")) is not int
            or value.get("kind") != "historical-resource-startup-metadata-only"
            or value.get("productionBaseCommit") != "6ee06aced87581e52aa301431f8996ed46d666b8"
            or value.get("localMetadataParent") != "91192b0bbfe6934c77af387234c6745b11492685"
            or value.get("actualAndroidExecution") is not False or value.get("runtimeAcceptance") is not False
            or type(value.get("sources")) is not dict or set(value["sources"]) != set(SOURCE_PATHS)):
        raise ValueError("Resource metadata provenance or owned scope differs")
    for row in value["sources"].values():
        if (type(row) is not dict or set(row) != {"previousSha256", "previousBytes", "currentSha256", "currentBytes", "edits"}
                or any(type(row[k]) is not str or re.fullmatch("[0-9a-f]{64}", row[k]) is None for k in ("previousSha256", "currentSha256"))
                or any(type(row[k]) is not int or not 0 < row[k] <= 256*1024 for k in ("previousBytes", "currentBytes"))
                or type(row["edits"]) is not list or not 0 < len(row["edits"]) <= 8):
            raise ValueError("Resource source metadata is not finite")
        for delta in row["edits"]:
            if (type(delta) is not dict or set(delta) != {"previous", "current"}
                    or any(type(delta[k]) is not str or not 0 < len(delta[k].encode()) <= 16384 for k in ("previous", "current"))
                    or delta["previous"] == delta["current"]):
                raise ValueError("Resource metadata context is not bounded and exact")
    return value

def source_input(raw, relative):
    if type(raw) is not bytes or type(relative) is not str or relative not in SOURCE_PATHS or not 0 < len(raw) <= 256*1024:
        raise ValueError("Resource metadata requires exact bounded complete source and owned path")
    row = config()["sources"][relative]
    identity = (_sha(raw), len(raw))
    if identity == (row["previousSha256"], row["previousBytes"]):
        return raw
    if identity != (row["currentSha256"], row["currentBytes"]):
        raise ValueError("Resource metadata rejects unknown complete source bytes")
    for delta in reversed(row["edits"]):
        current, previous = delta["current"].encode(), delta["previous"].encode()
        if raw.count(current) != 1:
            raise ValueError("Resource metadata requires each exact context once")
        raw = raw.replace(current, previous, 1)
    if (_sha(raw), len(raw)) != (row["previousSha256"], row["previousBytes"]):
        raise ValueError("Resource metadata failed to restore its complete actual predecessor")
    return raw

def prior_metadata_input(raw, relative):
    if relative not in (FINAL, LAYER):
        raise ValueError("Prior helper metadata accepts two exact helper paths only")
    return source_input(raw, relative)

def final_manifest_input(value):
    cfg = config()
    if type(value) is not dict or _sha(_encode(value)) != cfg["finalFixtureSha256"]:
        raise ValueError("Resource view requires the original complete 19-row fixture")
    result = copy.deepcopy(value)
    if result["files"][GV] != cfg["finalBefore"]:
        raise ValueError("Resource view lost the original whole Gecko row")
    result["files"][GV] = copy.deepcopy(cfg["finalAfter"])
    return result

def p2_current_input(raw, relative):
    if type(raw) is not bytes or relative != GV:
        raise ValueError("Resource P2 input requires the exact producer path")
    row = config()["sources"][GV]
    if (_sha(raw), len(raw)) == (row["currentSha256"], row["currentBytes"]):
        return source_input(raw, relative)
    # All other original preimages and unknown bytes face the unchanged P2
    # whole-image/context/predecessor guards; no unknown bytes are projected.
    return raw

def p2_reference_row(row):
    cfg = config()
    if (type(row) is not dict or type(row.get("deltas")) is not list or len(row["deltas"]) != 9
            or row["deltas"][4] != cfg["finalAfter"]["deltas"][4]):
        raise ValueError("Resource P2 view requires the exact combined manifest row")
    result = copy.deepcopy(row)
    if (row.get("reviewedSha256"), row.get("reviewedBytes")) == (cfg["finalAfter"]["reviewedSha256"], cfg["finalAfter"]["reviewedBytes"]):
        result["reviewedSha256"], result["reviewedBytes"] = cfg["finalBefore"]["reviewedSha256"], cfg["finalBefore"]["reviewedBytes"]
    result["deltas"][4] = copy.deepcopy(cfg["finalBefore"]["deltas"][4])
    return result

def frozen_manifest_input(value):
    cfg = config()
    if type(value) is not dict or _sha(_encode(value)) != cfg["finalAfterSha256"]:
        raise ValueError("Frozen resource metadata requires the complete combined 19-row image")
    result = copy.deepcopy(value)
    result["files"][GV] = copy.deepcopy(cfg["finalBefore"])
    return result

def root_manifest_input(value):
    cfg = config()
    if type(value) is not dict or _sha(_encode(value)) != cfg["rootBeforeSha256"]:
        raise ValueError("Resource helper view requires the complete original five-row input")
    result = copy.deepcopy(value)
    result["files"][FINAL] = copy.deepcopy(cfg["rootAfterRow"])
    return result
