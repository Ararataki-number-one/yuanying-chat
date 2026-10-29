"""Compile the production report and verify mobile evidence boundaries on the JVM."""
import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MobileIdentityConsistencyTest(unittest.TestCase):
    def test_observed_navigator_fields_and_existing_mobile_display_contract(self):
        configured = os.environ.get("PROFILE_JSON_JAR")
        candidates = [configured, ROOT / "work/profile-host/json.jar"]
        jar = next((Path(value) for value in candidates if value and Path(value).is_file()), None)
        if jar is None:
            self.fail("Set PROFILE_JSON_JAR to the existing functional org.json runtime")
        self.assertIn(hashlib.sha256(jar.read_bytes()).hexdigest(), {
            "3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796",
            "dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79",
        }, "Use one of the source-pinned JSON runtimes")
        java = os.environ.get("PROFILE_JAVA") or shutil.which("java")
        if not java:
            self.fail("Java 17 or PROFILE_JAVA is required")
        sources = [ROOT / "app/src/main/java/local/pocketchat/AuditReport.java",
                   ROOT / "app/src/main/java/local/pocketchat/BrowserIdentitySpec.java",
                   ROOT / "tests/browser-runtime/fingerprint-report-stubs/J.java",
                   ROOT / "tests/browser-runtime/fingerprint-report-stubs/BrowserNetworkGuard.java",
                   ROOT / "tests/mobile-identity-host/MobileIdentityConsistencyHost.java",
                   ROOT / "tests/browser-runtime/FingerprintTemplateTest.java"]
        with tempfile.TemporaryDirectory(prefix="mobile-identity-host-") as directory:
            compile_run = subprocess.run([java, "-m", "jdk.compiler/com.sun.tools.javac.Main",
                                          "--release", "8", "-encoding", "UTF-8", "-cp", str(jar),
                                          "-d", directory, *map(str, sources)], capture_output=True,
                                         text=True, timeout=30)
            self.assertEqual(compile_run.returncode, 0, compile_run.stdout + compile_run.stderr)
            reports = []
            for entry in ["MobileIdentityConsistencyHost", "FingerprintTemplateTest"]:
                run = subprocess.run([java, "-cp", directory + os.pathsep + str(jar),
                                      "local.pocketchat." + entry], capture_output=True, text=True, timeout=15)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                report = json.loads(run.stdout)
                self.assertEqual(report["status"], "passed")
                reports.append({"entry": entry, "status": report["status"],
                                "passed": report["passed"], "actualAndroidExecution": False,
                                "scope": report.get("scope", "")})
        print(json.dumps({"status": "passed", "runs": reports}, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
