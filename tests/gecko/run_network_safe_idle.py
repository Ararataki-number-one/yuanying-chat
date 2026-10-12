#!/usr/bin/env python3
"""One-shot actual Gecko gestures and controlled production network-transaction races."""
import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
import time

P = argparse.ArgumentParser()
P.add_argument("--adb", required=True)
P.add_argument("--serial", default="emulator-5554")
P.add_argument("--expected-apk-sha", default="")
A = P.parse_args()
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from gecko.network_sources_contract import verify_safe_idle as verify
OUT = ROOT / "work/gecko-integration"
OUT.mkdir(parents=True, exist_ok=True)
PKG = "local.pocketchat.test"
ACTIVITY = PKG + "/local.pocketchat.NetworkSafeIdleIntegrationActivity"
CASES = ["prepare-send", "capture-send", "prepare-transfer", "capture-navigation", "capture-delete", "complete-delete", "complete-late-save"]
GESTURES = []
EVENTS = []


def adb(*args, binary=False, timeout=35):
    return subprocess.check_output([A.adb, "-s", A.serial, *args], text=not binary, timeout=timeout)


def events():
    raw = adb("logcat", "-d", "-s", "PocketNetworkSafeIdle:I", "AndroidRuntime:E", "*:S")
    if "FATAL EXCEPTION" in raw:
        raise AssertionError(raw)
    found = []
    for line in raw.splitlines():
        if "PocketNetworkSafeIdle" not in line or "{" not in line:
            continue
        item = json.loads(line[line.index("{"):])
        found.append(item)
        if item.get("kind") == "result" and item.get("value", {}).get("status") != "passed":
            raise AssertionError(item)
    EVENTS[:] = found
    return found


def wait(kind, predicate=lambda v: True, seconds=80):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        for e in events():
            if e.get("kind") == kind and predicate(e.get("value", {})):
                return e["value"]
        time.sleep(.3)
    raise TimeoutError(f"Missing {kind}; final events={EVENTS[-5:]}")


def intent(action, *extras):
    return adb("shell", "am", "start", "-W", "-f", "0x20000000", "-n", ACTIVITY, "--es", "action", action, *extras)


def tap(value, name):
    css, native = value["css"], value["native"]
    assert css["width"] > 0 and css["height"] > 0 and native["width"] > 0 and native["height"] > 0
    sx, sy = native["width"] / css["width"], native["height"] / css["height"]
    assert abs(sx - sy) <= .12 * max(sx, sy), (css, native)
    x = round(native["x"] + css["x"] * sx)
    y = round(native["y"] + css["y"] * sy)
    assert native["x"] <= x < native["x"] + native["width"] and native["y"] <= y < native["y"] + native["height"]
    (OUT / f"network-safe-idle-{name}-before.png").write_bytes(adb("exec-out", "screencap", "-p", binary=True))
    command = ["shell", "input", "tap", str(x), str(y)]
    adb(*command)
    GESTURES.append({"case": name, "command": command, "x": x, "y": y, "bounds": value, "oneAttempt": True})



try:
    adb("shell", "am", "force-stop", PKG)
    adb("shell", "pm", "clear", PKG)
    adb("logcat", "-c")
    path = adb("shell", "pm", "path", PKG).strip().removeprefix("package:")
    apk_sha = adb("shell", "sha256sum", path).split()[0]
    assert len(apk_sha) == 64 and (not A.expected_apk_sha or apk_sha == A.expected_apk_sha)
    adb("shell", "am", "start", "-W", "-n", ACTIVITY)
    ready = wait("ready", lambda v: v.get("cases") == CASES, seconds=200)
    for index, name in enumerate(CASES):
        intent("begin", "--ei", "case", str(index))
        if name != "complete-delete":
            phase = wait("phase", lambda v, name=name: v.get("case") == name)
            if name.endswith("send"):
                tap(wait("tapNeeded", lambda v, name=name: v.get("case") == name), name)
            else:
                wait("injectionNeeded", lambda v, name=name: v.get("case") == name)
            intent("release", "--es", "name", name)
        wait("case", lambda v, name=name: v.get("name") == name)
        wait("ready", lambda v, index=index: v.get("completedCases") == index + 1)
    intent("finish")
    wait("result", lambda v: v.get("status") == "passed")
    raw = adb("exec-out", "content", "read", "--uri", "content://" + PKG + ".evidence/network-safe-idle")
    report = json.loads(raw)
    report.update(sourceCommit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), installedPackage=PKG, installedApkSha256=apk_sha, actualAndroidGestures=GESTURES, phaseEvents=EVENTS, runnerOneAttemptPerGesture=True)
    (OUT / "network-safe-idle-results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    receipt = json.loads((ROOT / "third-party/patches/mihomo-v1.19.31-probe-build.json").read_text())
    assert report["coreAbi"] == "x86_64"
    assert report["coreVersion"] == receipt["recipe"]["version"]
    assert report["coreSha256"] == receipt["binaries"]["x86_64"]["sha256"]
    verify(report)
    (OUT / "network-safe-idle-final.png").write_bytes(adb("exec-out", "screencap", "-p", binary=True))
    (OUT / "network-safe-idle-log.txt").write_text(adb("logcat", "-d"))
    print(json.dumps({"status": "passed", "checkCount": report["checkCount"], "cases": len(report["cases"]), "realTrustedGestures": len(GESTURES), "report": str(OUT / "network-safe-idle-results.json")}))
except BaseException as error:
    (OUT / "network-safe-idle-runner-failure.json").write_text(json.dumps({"status": "failed", "sourceCommit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "error": str(error), "events": EVENTS, "gestures": GESTURES}, ensure_ascii=False, indent=2) + "\n")
    try:
        (OUT / "network-safe-idle-failure-log.txt").write_text(adb("logcat", "-d"))
        (OUT / "network-safe-idle-failure.png").write_bytes(adb("exec-out", "screencap", "-p", binary=True))
    except Exception:
        pass
    raise
