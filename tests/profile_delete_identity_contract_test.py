"""Deletion identity and actual maintenance-lease regressions.

Catalogue execution uses the existing deterministic transactional adapter;
filesystem/thread/process checks use the production lease on a local filesystem.
These do not claim Android, account-login, or physical-device acceptance.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROD = ROOT / "app/src/main/java/local/pocketchat"
HERE = ROOT / "tests/default-environment-host"
spec = importlib.util.spec_from_file_location("delete_existing_host", HERE / "run.py")
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)


class DeleteIdentityContractTest(unittest.TestCase):
    def java(self):
        java = os.environ.get("PROFILE_JAVA") or shutil.which("java")
        self.assertTrue(java, "JDK 17 with jdk.compiler is required")
        return str(java)

    def test_exact_catalogue_rejects_stale_confirmation_and_worker(self):
        jar = next((Path(x) for x in [os.environ.get("PROFILE_JSON_JAR"),
                    ROOT / "work/profile-host/json.jar", ROOT / "work/profile-host/android-json.jar"]
                    if x and Path(x).is_file()), None)
        self.assertIsNotNone(jar, "A source-pinned JSON runtime is required")
        self.assertIn(hashlib.sha256(jar.read_bytes()).hexdigest(), {
            "3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796",
            "dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79"})
        catalog = (PROD / "ProfileCatalog.java").read_text()
        methods = ["JSONObject item(", "static JSONObject row(", "JSONArray list(",
                   "EnvironmentSpec.Identity identity(", "boolean available(", "void opened(",
                   "void created(", "void beginDelete(", "void completeDelete(int slot)",
                   "EnvironmentSpec.Identity beginDelete(EnvironmentSpec.Identity expected)",
                   "EnvironmentSpec.Identity deletionIdentity(",
                   "void completeDelete(EnvironmentSpec.Identity expected)"]
        text = (HERE / "DefaultEnvironmentHost.java").read_text().replace(
            "/* CATALOG */", "\n".join(host.member(catalog, key) for key in methods)).replace(
            "/* IDENTITY */", host.member((PROD / "EnvironmentSpec.java").read_text(), "static final class Identity")).replace(
            "/* BRAND */", host.member((PROD / "BrandLaunchActivity.java").read_text(), "void route(")).replace(
            "/* OPEN_WINDOW */", host.member((PROD / "WindowHomeActivity.java").read_text(), "void openWindow("))
        text += "\nclass EnvironmentDeleteActivity{static final class Expired extends java.io.IOException{}\n" + host.member(
            (PROD / "EnvironmentDeleteActivity.java").read_text(), "static void requireCurrent(") + "}\n"
        text = text.replace("import android.app.Activity;", "import java.io.IOException;import android.app.Activity;")
        with tempfile.TemporaryDirectory(prefix="delete-identity-host-") as directory:
            base = Path(directory)
            (base / "DefaultEnvironmentHost.java").write_text(text)
            sources = [base / "DefaultEnvironmentHost.java", HERE / "DeleteIdentityCases.java",
                       PROD / "AppSettings.java", PROD / "WorkspaceNavigation.java",
                       *HERE.glob("stubs/**/*.java")]
            compiled = subprocess.run([self.java(), "-m", "jdk.compiler/com.sun.tools.javac.Main",
                "-encoding", "UTF-8", "-cp", str(jar), "-d", directory, *map(str, sources)],
                text=True, capture_output=True, timeout=30)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            result = subprocess.run([self.java(), "-cp", directory + os.pathsep + str(jar),
                "local.pocketchat.DeleteIdentityCases"], text=True, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "passed")
            self.assertFalse(report["actualAndroidExecution"])
            self.assertTrue(all(row["pass"] for row in report["checks"]))
            self.assertGreaterEqual(report["passed"], 12)
            print(json.dumps({"status": "passed", "catalogueChecks": report["passed"],
                              "actualAndroidExecution": False}))

    def test_production_lease_serializes_real_threads_and_processes(self):
        with tempfile.TemporaryDirectory(prefix="maintenance-lease-host-") as directory:
            classes = Path(directory) / "classes"
            root = Path(directory) / "app-no-backup"
            root.mkdir()
            result = subprocess.run([self.java(), "-m", "jdk.compiler/com.sun.tools.javac.Main",
                "--release", "8", "-encoding", "UTF-8", "-d", str(classes),
                str(PROD / "EnvironmentMaintenanceLease.java"),
                str(ROOT / "tests/browser-runtime/EnvironmentMaintenanceLeaseHost.java")],
                text=True, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([self.java(), "-cp", str(classes),
                "local.pocketchat.EnvironmentMaintenanceLeaseHost", str(root)],
                text=True, capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "passed")
            self.assertTrue(report["actualProductionLeaseExecution"])
            self.assertFalse(report["actualAndroidExecution"])
            self.assertGreaterEqual(report["passed"], 12)

    def test_production_intents_and_cleanup_keep_exact_identity(self):
        ui = (PROD / "WindowHomeActivity.java").read_text()
        dialog = host.member(ui, "void deleteEnvironment(")
        self.assertIn("beginDelete(shown)", dialog)
        self.assertNotIn("beginDelete(id)", dialog)
        intent = host.member(ui, "void startDelete(")
        for field in ["expected.slot", "expected.generation", "expected.environmentId"]:
            self.assertIn(field, intent)
        self.assertIn('startDelete(new EnvironmentSpec.Identity(id,deleted.optInt("generation"),deleted.getString("environmentId")))', ui)
        deletion = (PROD / "EnvironmentDeleteActivity.java").read_text()
        outer = host.member(deletion, "static void remove(Context c,EnvironmentSpec.Identity expected)")
        body = host.member(deletion, "private static void performRemove(")
        self.assertIn("EnvironmentMaintenanceLease.with", outer)
        self.assertIn("performRemove(c,expected.slot,expected)", outer)
        self.assertNotIn("beginTransaction", body)
        self.assertEqual(body.count("requireCurrent(catalog,expected)"), 2)
        first, last = body.index("requireCurrent(catalog,expected)"), body.rindex("requireCurrent(catalog,expected)")
        self.assertLess(first, body.index('"stopForDelete"'))
        self.assertGreater(last, body.index("Thread.sleep(100);}while(true);"))
        self.assertLess(last, body.index("NotificationManager notices="))
        self.assertIn("catalog.completeDelete(expected)", body)
        self.assertNotIn("catalog.completeDelete(slot)", body)
        reset = host.member((PROD / "EnvironmentResetActivity.java").read_text(), "static void reset(")
        self.assertIn("EnvironmentMaintenanceLease.with", reset)
        self.assertIn("Profiles.global(c).getNoBackupFilesDir()", reset)

    def test_delete_and_reset_retire_the_actual_encrypted_audit_record(self):
        audit = (PROD / "EnvironmentAudit.java").read_text()
        self.assertIn('store.get("environment-audit")', audit)
        secret = (PROD / "SecretStore.java").read_text()
        self.assertIn('slot+".sealed"', host.member(secret, "File file("))
        deletion = host.member((PROD / "EnvironmentDeleteActivity.java").read_text(), "private static void performRemove(")
        self.assertIn('"browser-reset","environment-audit"', deletion)
        reset = host.member((PROD / "EnvironmentResetActivity.java").read_text(), "private static void performReset(")
        self.assertIn('new SecretStore(profile).remove("environment-audit")', reset)
        self.assertLess(reset.index("terminate(c,slot)"), reset.index('remove("environment-audit")'))
        self.assertLess(reset.index('remove("environment-audit")'), reset.index("repository.finishLoginReset(plan)"))


if __name__ == "__main__":
    unittest.main()
