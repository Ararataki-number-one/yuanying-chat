"""Production manual progress/reference overview; no browser or device execution."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = ROOT / "app/src/main/java/local/pocketchat"
SOURCES = [PRODUCTION / name for name in (
    "FingerprintReportComparison.java", "FingerprintContextBaselines.java",
    "FingerprintDeepBaseline.java", "FingerprintObservationHistory.java",
    "AuditReport.java", "BrowserIdentitySpec.java", "J.java")]
SOURCES += [ROOT / name for name in (
    "tests/browser-runtime/fingerprint-report-stubs/BrowserNetworkGuard.java",
    "tests/fingerprint-baseline-host/FingerprintDeepBaselineHost.java",
    "tests/fingerprint-context-baseline-host/FingerprintContextBaselinesHost.java",
    "tests/fingerprint-comparison-host/FingerprintReportComparisonHost.java",
    "tests/fingerprint-followup-progress-host/FingerprintFollowupProgressHost.java")]
PINS = {"desktop": ("PROFILE_JSON_JAR", "json.jar", "3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796"),
        "android-json": ("PROFILE_ANDROID_JSON_JAR", "android-json.jar", "dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79")}


class FingerprintFollowupProgressTest(unittest.TestCase):
    def test_owned_manual_progress_and_reference_overview(self):
        java = os.environ.get("PROFILE_JAVA") or shutil.which("java")
        self.assertTrue(java, "JDK17+ is required")
        # v27's production report may use this optional adjacent pure-Java helper.
        sources = SOURCES + [p for p in [PRODUCTION / "MobileIdentityConsistency.java"] if p.is_file()]
        before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
        runs = []
        for runtime, (variable, filename, pin) in PINS.items():
            jar = Path(os.environ.get(variable, str(ROOT / "work/profile-host" / filename)))
            self.assertTrue(jar.is_file(), "Pinned dependency required: " + runtime)
            self.assertEqual(hashlib.sha256(jar.read_bytes()).hexdigest(), pin)
            with tempfile.TemporaryDirectory(prefix="fingerprint-followup-progress-") as classes:
                compiled = subprocess.run([java, "-m", "jdk.compiler/com.sun.tools.javac.Main", "--release", "8", "-encoding", "UTF-8", "-cp", str(jar), "-d", classes, *map(str, sources)], capture_output=True, text=True, timeout=40)
                self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
                run = subprocess.run([java, "-cp", classes + os.pathsep + str(jar), "local.pocketchat.FingerprintFollowupProgressHost"], capture_output=True, text=True, timeout=20)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                report = json.loads(run.stdout)
                self.assertEqual(report["status"], "passed")
                self.assertGreaterEqual(report["passed"], 25)
                self.assertEqual(report["passed"], report["total"])
                self.assertEqual(report["passed"], len(report["checks"]))
                self.assertTrue(all(item["pass"] is True for item in report["checks"]))
                for flag in ("actualAndroidExecution", "actualGeckoExecution", "physicalPhoneAcceptance", "protectionEffectivenessAcceptance"):
                    self.assertIs(report[flag], False)
                runs.append({"runtime": runtime, "report": report})
        self.assertEqual(before, {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
        output = ROOT / "work/fingerprint-followup-progress/host-results.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({"status": "passed", "sourceSha256": before, "runs": runs}, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    unittest.main()
