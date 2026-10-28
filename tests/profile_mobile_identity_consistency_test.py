"""Compile the production report and verify mobile evidence boundaries on the JVM."""
import json
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
        candidates = [configured, ROOT / "work/profile-host/json.jar",
                      Path("/workspace/yuanying-chat/work/audit-20261023/host/json-20240303.jar")]
        jar = next((Path(value) for value in candidates if value and Path(value).is_file()), None)
        if jar is None:
            self.fail("Set PROFILE_JSON_JAR to the existing functional org.json runtime")
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
