"""Production filesystem root admission and destructive-delete ordering checks.

These are JVM/source checks, not Android deletion or phone acceptance evidence.
The original 39 lifecycle host controls and device producer remain unchanged.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "app/src/main/java/local/pocketchat"


def remove_body():
    text = (SOURCE / "EnvironmentDeleteActivity.java").read_text()
    start = text.index("private static void performRemove(Context c,int slot,EnvironmentSpec.Identity expected)throws Exception{")
    end = text.index("  static void erase(File f)", start)
    return text[start:end]


class EnvironmentDeleteRootGuardTest(unittest.TestCase):
    def test_actual_root_policy_on_real_filesystem(self):
        java = os.environ.get("PROFILE_JAVA") or shutil.which("java")
        self.assertTrue(java, "JDK 17+ with jdk.compiler is required")
        with tempfile.TemporaryDirectory(prefix="environment-delete-root-classes-") as output:
            subprocess.run([
                java, "-m", "jdk.compiler/com.sun.tools.javac.Main", "-encoding", "UTF-8",
                "-source", "8", "-target", "8", "-d", output,
                str(SOURCE / "EnvironmentBrowserData.java"),
                str(ROOT / "tests/browser-runtime/EnvironmentDeleteRootPolicyTest.java"),
            ], cwd=ROOT, check=True, capture_output=True, text=True)
            execution = subprocess.run([
                java, "-cp", output, "local.pocketchat.EnvironmentDeleteRootPolicyTest",
            ], cwd=ROOT, check=True, capture_output=True, text=True)
        result = json.loads(execution.stdout)
        self.assertEqual(result, dict(status="passed", passed=8,
            actualAndroidExecution=False, actualProductionRootPolicyExecution=True))

    def test_first_guard_precedes_all_delete_side_effects(self):
        body = remove_body()
        first_statement = body[body.index("{") + 1:].lstrip()
        self.assertTrue(first_statement.startswith("EnvironmentResetActivity.verifyRoots(c,slot);"))
        first_guard = body.index("EnvironmentResetActivity.verifyRoots(c,slot);")
        for side_effect in ["ProfileCatalog.get(c)", "Profiles.context(c,slot)",
                "DownloadLibrary.get(c).migrateBeforeRemoval(slot)", "new NetworkCatalog(c)",
                '"stopForDelete"']:
            self.assertLess(first_guard, body.index(side_effect), side_effect)

    def test_second_guard_follows_writer_exit_and_precedes_enumeration(self):
        body = remove_body()
        guards = list(re.finditer(re.escape("EnvironmentResetActivity.verifyRoots(c,slot);"), body))
        self.assertEqual(len(guards), 2)
        second = guards[1].start()
        # The guard must follow the entire bounded stop/kill loop, including
        # its successful !alive exit, not just its first kill attempt.
        self.assertLess(body.index('"stopForDelete"'), second)
        self.assertLess(body.index("android.os.Process.killProcess(p.pid)"), second)
        self.assertLess(body.index("Thread.sleep(100);}while(true);"), second)
        migration = body.index("DownloadLibrary.get(c).migrateBeforeRemoval(slot)")
        self.assertLess(second, migration)
        for destructive_step in ["NotificationManager notices=", "files.listFiles()",
                'erase(new File(data,"cache/profiles/env"+slot))',
                'erase(new File(profile.getNoBackupFilesDir(),name))',
                'EnvironmentResetActivity.removeLoginDatabases(profile)', "catalog.completeDelete(expected)"]:
            self.assertLess(migration, body.index(destructive_step), destructive_step)


    def test_default_deletion_clears_private_share_snapshots_after_writers_exit(self):
        body = remove_body()
        default = body.index("else{\n      EnvironmentBrowserData.clear(")
        end = body.index("// System WebView", default)
        cleanup = "EnvironmentBrowserData.clearNetworkShareSnapshots(profile.getNoBackupFilesDir())"
        self.assertEqual(body.count(cleanup), 1)
        self.assertIn("NetworkSourceSelection.withActiveSnapshot(profile,()->{", body[default:end])
        self.assertIn(cleanup, body[default:end])
        self.assertLess(body.index("Thread.sleep(100);}while(true);"), body.index(cleanup))
        self.assertLess(body.index(cleanup), body.index("catalog.completeDelete(expected)"))

    def test_login_reset_retires_the_separate_gecko_address_in_its_durable_edit(self):
        reset = (SOURCE / "EnvironmentResetActivity.java").read_text()
        start = reset.index("private static void performReset(")
        removed = reset.index('for(String key:new String[]{"pending","legacyPending"', start)
        commit = reset.index("if(!preferences.commit()", removed)
        self.assertLess(reset.index("terminate(c,slot)", start), removed)
        self.assertIn('"geckoBrowserUrl"', reset[removed:commit])
        self.assertNotIn('"browserHomeUrl"', reset[removed:commit])
        self.assertLess(commit, reset.index("repository.finishLoginReset(plan)", start))


    def test_login_databases_are_checked_before_both_maintenance_acks(self):
        delete = remove_body()
        cleanup = "EnvironmentResetActivity.removeLoginDatabases(profile)"
        self.assertLess(delete.rindex("requireCurrent(catalog,expected)"), delete.index(cleanup))
        self.assertLess(delete.index(cleanup), delete.index("catalog.completeDelete(expected)"))
        reset = (SOURCE / "EnvironmentResetActivity.java").read_text()
        start = reset.index("private static void performReset(")
        self.assertLess(reset.index("terminate(c,slot)", start), reset.index("removeLoginDatabases(profile)", start))
        self.assertLess(reset.index("removeLoginDatabases(profile)", start), reset.index("repository.finishLoginReset(plan)", start))

    def test_actual_database_retirement_check_retries_residual_files(self):
        java = os.environ.get("PROFILE_JAVA") or shutil.which("java")
        self.assertTrue(java, "JDK 17+ with jdk.compiler is required")
        reset = (SOURCE / "EnvironmentResetActivity.java").read_text()
        start = reset.index("  static void removeLoginDatabases(")
        end = reset.index("\n  }", start) + len("\n  }")
        ledger = (SOURCE / "ReplyNoticeLedger.java").read_text()
        database = re.search(r'static final String DATABASE="([^"]+)";', ledger)
        self.assertIsNotNone(database)
        with tempfile.TemporaryDirectory(prefix="environment-retire-databases-") as temp:
            work = Path(temp)
            owner = work / "EnvironmentResetActivity.java"
            owner.write_text(
                "package local.pocketchat; import java.io.*; final class EnvironmentResetActivity {\n"
                + reset[start:end] + "\n}\nfinal class ReplyNoticeLedger { static final String DATABASE="
                + json.dumps(database.group(1)) + "; }\n"
            )
            fixture = ROOT / "tests/browser-runtime/EnvironmentDatabaseRetirementCases.java"
            subprocess.run([
                java, "-m", "jdk.compiler/com.sun.tools.javac.Main", "-encoding", "UTF-8",
                "-source", "8", "-target", "8", "-d", temp, str(owner), str(fixture),
            ], cwd=ROOT, check=True, capture_output=True, text=True, timeout=20)
            result = subprocess.run([
                java, "-cp", temp, "local.pocketchat.EnvironmentDatabaseRetirementCases", str(work / "fixture"),
            ], cwd=ROOT, check=True, capture_output=True, text=True, timeout=20)
        self.assertEqual(json.loads(result.stdout), dict(status="passed", checks=18, actualAndroidExecution=False))


if __name__ == "__main__":
    unittest.main()
